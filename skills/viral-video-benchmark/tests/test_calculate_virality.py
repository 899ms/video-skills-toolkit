import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_DIR / "scripts" / "calculate_virality.py"


def load_module():
    spec = importlib.util.spec_from_file_location("calculate_virality", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_payload(platform="douyin", followers="10万", target_likes="8000", core_values=None):
    core_values = core_values or ["1000"] * 10
    recent_posts = []
    for index, value in enumerate(core_values):
        post = {"post_id": f"recent-{index}", "likes_raw": value}
        if platform in {"xhs", "xiaohongshu"}:
            post["collects_raw"] = "0"
        recent_posts.append(post)

    target = {"post_id": "target", "likes_raw": target_likes}
    if platform in {"xhs", "xiaohongshu"}:
        target["collects_raw"] = "0"

    return {
        "schema_version": 1,
        "platform": platform,
        "followers_raw": followers,
        "target": target,
        "recent_posts": recent_posts,
    }


class CountParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_parses_supported_formats(self):
        cases = {
            "289": (289, False),
            "1,234": (1234, False),
            "1.6万": (16000, True),
            "3.5w": (35000, True),
            "2W+": (20000, True),
            "289+": (289, True),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                parsed = self.module.parse_count(raw, "count")
                self.assertEqual((parsed.value, parsed.rounded_source), expected)

    def test_rejects_ambiguous_or_invalid_counts(self):
        for raw in (None, "", "1.5", "abc", -1, True):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.module.parse_count(raw, "count")


class ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_tier_boundaries(self):
        cases = [(9999, "S"), (10000, "A"), (99999, "A"), (100000, "B"), (999999, "B"), (1000000, "C")]
        for followers, expected in cases:
            with self.subTest(followers=followers):
                self.assertEqual(self.module.follower_tier(followers)[0], expected)

    def test_selects_highest_jointly_satisfied_grade(self):
        payload = make_payload(followers="10万", target_likes="16000")
        result = self.module.calculate(payload)
        self.assertEqual(result["grade"], "爆款")
        self.assertEqual(result["scores"]["R"], 16.0)
        self.assertEqual(result["scores"]["M"], 0.16)
        self.assertTrue(result["deep_process"])

    def test_phenomenon_grade(self):
        payload = make_payload(followers="10万", target_likes="30000")
        result = self.module.calculate(payload)
        self.assertEqual(result["grade"], "现象级")

    def test_account_anomaly_without_breakout_is_ordinary(self):
        payload = make_payload(followers="100万", target_likes="30000", core_values=["100"] * 10)
        result = self.module.calculate(payload)
        self.assertEqual(result["grade"], "普通")
        self.assertIn("未破圈", result["reason"])

    def test_xiaohongshu_uses_likes_plus_collections(self):
        payload = make_payload(platform="xhs", followers="1万", target_likes="3000", core_values=["500"] * 10)
        payload["target"]["collects_raw"] = "3000"
        for post in payload["recent_posts"]:
            post["collects_raw"] = "500"
        result = self.module.calculate(payload)
        self.assertEqual(result["platform"], "xiaohongshu")
        self.assertEqual(result["target"]["core_metric"], 6000)
        self.assertEqual(result["baseline"]["median"], 1000.0)
        self.assertEqual(result["grade"], "爆款")

    def test_low_confidence_requires_confirmation(self):
        payload = make_payload(followers="1万", target_likes="5000", core_values=["500"] * 7)
        result = self.module.calculate(payload)
        self.assertEqual(result["baseline"]["confidence"], "low")
        self.assertTrue(result["eligible_for_deep_process"])
        self.assertTrue(result["requires_confirmation"])
        self.assertFalse(result["deep_process"])

    def test_live_followers_define_main_benchmark_pool(self):
        payload = make_payload(followers="2万", target_likes="8000")
        payload["benchmark_context"] = {
            "own_followers_raw": "1000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }
        payload["target"]["views_raw"] = "40万"

        result = self.module.calculate(payload)
        account_pool = result["benchmark"]["account_pool"]
        view_breakout = result["benchmark"]["view_breakout"]

        self.assertEqual(account_pool["status"], "main_pool")
        self.assertEqual(account_pool["main_pool_max_followers"], 20000)
        self.assertEqual(view_breakout["status"], "passed")
        self.assertEqual(view_breakout["view_to_follower_ratio"], 20.0)
        self.assertEqual(result["benchmark"]["candidate_status"], "main_pool_candidate")

    def test_accounts_above_twenty_times_enter_inspiration_pool(self):
        payload = make_payload(followers="2.1万", target_likes="10000")
        payload["benchmark_context"] = {
            "own_followers_raw": "1000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }
        payload["target"]["views_raw"] = "42万"

        result = self.module.calculate(payload)

        self.assertEqual(result["benchmark"]["account_pool"]["status"], "inspiration_pool")
        self.assertEqual(result["benchmark"]["candidate_status"], "inspiration_pool_candidate")
        self.assertTrue(result["eligible_for_deep_process"])

    def test_view_filter_failure_does_not_change_R_M_grade(self):
        payload = make_payload(followers="1000", target_likes="500", core_values=["50"] * 10)
        payload["benchmark_context"] = {
            "own_followers_raw": "1000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }
        payload["target"]["views_raw"] = "5000"

        result = self.module.calculate(payload)

        self.assertEqual(result["grade"], "爆款")
        self.assertTrue(result["deep_process"])
        self.assertEqual(result["benchmark"]["view_breakout"]["status"], "failed")
        self.assertEqual(result["benchmark"]["candidate_status"], "rejected_by_view_filter")

    def test_twenty_times_views_still_requires_ten_thousand_absolute_views(self):
        payload = make_payload(followers="100", target_likes="100", core_values=["10"] * 10)
        payload["target"]["views_raw"] = "2000"

        result = self.module.calculate(payload)
        view_breakout = result["benchmark"]["view_breakout"]

        self.assertTrue(view_breakout["meets_ratio"])
        self.assertFalse(view_breakout["meets_minimum_views"])
        self.assertEqual(view_breakout["status"], "failed")

    def test_missing_views_falls_back_to_R_M(self):
        payload = make_payload(followers="1000", target_likes="500", core_values=["50"] * 10)
        payload["benchmark_context"] = {
            "own_followers_raw": "1000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }

        result = self.module.calculate(payload)

        self.assertEqual(result["benchmark"]["view_breakout"]["status"], "unavailable")
        self.assertEqual(result["benchmark"]["candidate_status"], "main_pool_candidate")

    def test_benchmark_context_requires_observation_time(self):
        payload = make_payload()
        payload["benchmark_context"] = {"own_followers_raw": "1000"}
        with self.assertRaises(ValueError):
            self.module.calculate(payload)

    def test_confidence_boundaries_and_latest_twenty_limit(self):
        for count, expected in ((5, "low"), (9, "low"), (10, "normal"), (20, "normal"), (21, "normal")):
            with self.subTest(count=count):
                payload = make_payload(core_values=["100"] * count)
                result = self.module.calculate(payload)
                self.assertEqual(result["baseline"]["confidence"], expected)
                self.assertEqual(result["baseline"]["sample_count"], min(count, 20))

    def test_odd_and_even_medians(self):
        odd = self.module.calculate(make_payload(core_values=["1", "3", "100", "101", "102"]))
        even = self.module.calculate(make_payload(core_values=["1", "3", "100", "101", "102", "103"]))
        self.assertEqual(odd["baseline"]["median"], 100.0)
        self.assertEqual(even["baseline"]["median"], 100.5)

    def test_insufficient_baseline_has_no_formal_grade(self):
        payload = make_payload(followers="1万", target_likes="5000", core_values=["500"] * 4)
        result = self.module.calculate(payload)
        self.assertIsNone(result["grade"])
        self.assertIsNone(result["scores"]["R"])
        self.assertEqual(result["baseline"]["confidence"], "insufficient")

    def test_excludes_target_duplicates_and_pinned_posts(self):
        payload = make_payload(core_values=["1000"] * 10)
        payload["recent_posts"].extend(
            [
                {"post_id": "target", "likes_raw": "999999"},
                {"post_id": "recent-0", "likes_raw": "999999"},
                {"post_id": "pinned", "likes_raw": "999999", "pinned": True},
            ]
        )
        result = self.module.calculate(payload)
        self.assertEqual(result["baseline"]["sample_count"], 10)
        self.assertEqual(len(result["baseline"]["excluded"]), 3)

    def test_pinned_duplicate_cannot_contaminate_baseline_in_either_order(self):
        control = self.module.calculate(make_payload(core_values=["1000"] * 10))
        for duplicate_posts, expected_reasons in (
            (
                [
                    {"post_id": "pinned-duplicate", "likes_raw": "1"},
                    {"post_id": "pinned-duplicate", "likes_raw": "999999", "pinned": True},
                ],
                ["pinned_duplicate", "pinned"],
            ),
            (
                [
                    {"post_id": "pinned-duplicate", "likes_raw": "999999", "pinned": True},
                    {"post_id": "pinned-duplicate", "likes_raw": "1"},
                ],
                ["pinned", "pinned_duplicate"],
            ),
        ):
            with self.subTest(duplicate_posts=duplicate_posts):
                payload = make_payload(core_values=["1000"] * 10)
                payload["recent_posts"].extend(duplicate_posts)

                result = self.module.calculate(payload)

                self.assertEqual(result["baseline"]["median"], control["baseline"]["median"])
                self.assertEqual(result["grade"], control["grade"])
                self.assertNotIn(
                    "pinned-duplicate", [post["post_id"] for post in result["baseline"]["included"]]
                )
                self.assertEqual(
                    [item["reason"] for item in result["baseline"]["excluded"]], expected_reasons
                )

    def test_requires_xiaohongshu_collections(self):
        payload = make_payload(platform="xhs")
        del payload["recent_posts"][0]["collects_raw"]
        with self.assertRaises(ValueError):
            self.module.calculate(payload)

    def test_rejects_zero_followers_and_zero_baseline(self):
        with self.assertRaises(ValueError):
            self.module.calculate(make_payload(followers="0"))
        with self.assertRaises(ValueError):
            self.module.calculate(make_payload(core_values=["0"] * 10))

    def test_cli_output_is_deterministic_json(self):
        payload = make_payload(target_likes="8000")
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, str(SCRIPT_PATH), "--input", str(input_path)]
            first = subprocess.run(command, capture_output=True, text=True, check=True)
            second = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(first.stdout, second.stdout)
        json.loads(first.stdout)


if __name__ == "__main__":
    unittest.main()
