import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_recent_posts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("scan_recent_posts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_payload(count=20, platform="douyin"):
    posts = []
    for index in range(count):
        post = {"post_id": f"post-{index}", "likes_raw": "1000", "title": f"标题 {index}"}
        if platform == "xiaohongshu":
            post["collects_raw"] = "0"
        posts.append(post)
    return {
        "schema_version": 1,
        "platform": platform,
        "followers_raw": "10万",
        "recent_posts": posts,
    }


class ScanRecentPostsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_finds_qualifying_post_without_model_arithmetic(self):
        payload = make_payload()
        payload["recent_posts"][4]["likes_raw"] = "24000"
        result = self.module.scan(payload)

        self.assertEqual(result["scan_sample_count"], 20)
        self.assertEqual(result["results"][4]["grade"], "现象级")
        self.assertEqual(result["results"][4]["baseline_sample_count"], 19)
        self.assertNotIn("post-4", result["results"][4]["baseline_post_ids"])
        self.assertEqual(len(set(result["results"][4]["baseline_post_ids"])), 19)
        self.assertEqual(result["results"][4]["url"], "https://www.douyin.com/video/post-4")
        self.assertEqual([item["post_id"] for item in result["qualifying"]], ["post-4"])
        self.assertEqual(result["grade_counts"], {"普通": 19, "小爆": 0, "爆款": 0, "现象级": 1, "未判级": 0})
        self.assertTrue(result["requires_user_selection_for_deep_process"])

    def test_low_confidence_candidates_require_selection_before_deep_processing(self):
        payload = make_payload(count=7)
        payload["recent_posts"][0]["likes_raw"] = "50000"
        result = self.module.scan(payload)
        candidate = result["results"][0]

        self.assertEqual(candidate["baseline_confidence"], "low")
        self.assertTrue(candidate["eligible_for_deep_process"])
        self.assertTrue(candidate["requires_confirmation"])
        self.assertFalse(candidate["deep_process"])

    def test_scan_separates_main_pool_and_inspiration_candidates(self):
        main_payload = make_payload()
        main_payload["followers_raw"] = "2万"
        main_payload["benchmark_context"] = {
            "own_followers_raw": "1000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }
        main_payload["recent_posts"][4]["likes_raw"] = "8000"
        main_payload["recent_posts"][4]["views_raw"] = "40万"

        main_result = self.module.scan(main_payload)

        self.assertEqual(main_result["account_pool"]["status"], "main_pool")
        self.assertEqual([item["post_id"] for item in main_result["benchmark_candidates"]], ["post-4"])
        self.assertEqual(main_result["benchmark_candidates"][0]["view_breakout"]["status"], "passed")

        inspiration_payload = make_payload()
        inspiration_payload["benchmark_context"] = {
            "own_followers_raw": "1000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }
        inspiration_payload["recent_posts"][4]["likes_raw"] = "24000"

        inspiration_result = self.module.scan(inspiration_payload)

        self.assertEqual(inspiration_result["account_pool"]["status"], "inspiration_pool")
        self.assertEqual(
            [item["post_id"] for item in inspiration_result["inspiration_candidates"]], ["post-4"]
        )

    def test_scan_keeps_R_M_grade_when_view_filter_rejects_candidate(self):
        payload = make_payload()
        payload["benchmark_context"] = {
            "own_followers_raw": "5000",
            "own_followers_observed_at": "2026-07-17T22:30:00+08:00",
        }
        payload["recent_posts"][4]["likes_raw"] = "24000"
        payload["recent_posts"][4]["views_raw"] = "1000"

        result = self.module.scan(payload)

        self.assertEqual(result["results"][4]["grade"], "现象级")
        self.assertEqual([item["post_id"] for item in result["view_filter_rejected"]], ["post-4"])
        self.assertEqual([item["post_id"] for item in result["qualifying"]], ["post-4"])

    def test_fewer_than_six_posts_cannot_produce_formal_scan_grades(self):
        result = self.module.scan(make_payload(count=5))
        self.assertTrue(all(item["grade"] is None for item in result["results"]))
        self.assertEqual(result["grade_counts"]["未判级"], 5)

    def test_scan_confidence_boundaries(self):
        for count, expected in ((6, "low"), (10, "low"), (11, "normal")):
            with self.subTest(count=count):
                result = self.module.scan(make_payload(count=count))
                self.assertTrue(all(item["baseline_confidence"] == expected for item in result["results"]))

    def test_excludes_pinned_duplicates_and_limits_window_to_twenty(self):
        payload = make_payload(count=22)
        payload["recent_posts"].insert(0, {"post_id": "pinned", "likes_raw": "999999", "pinned": True})
        payload["recent_posts"].insert(1, {"post_id": "post-0", "likes_raw": "999999"})
        result = self.module.scan(payload)

        self.assertEqual(result["scan_sample_count"], 20)
        self.assertEqual(result["results"][0]["post_id"], "post-0")
        self.assertEqual(result["results"][0]["likes"], 999999)
        self.assertEqual(len(result["excluded"]), 4)

    def test_pinned_id_cannot_reenter_through_unpinned_duplicate(self):
        payload = make_payload(count=20)
        payload["recent_posts"].insert(0, {"post_id": "post-0", "likes_raw": "999999", "pinned": True})
        result = self.module.scan(payload)

        self.assertNotIn("post-0", [item["post_id"] for item in result["results"]])
        self.assertEqual(result["scan_sample_count"], 19)

    def test_xiaohongshu_requires_collections_for_every_candidate(self):
        payload = make_payload(platform="xiaohongshu")
        del payload["recent_posts"][3]["collects_raw"]
        with self.assertRaises(ValueError):
            self.module.scan(payload)

    def test_xiaohongshu_scan_uses_likes_plus_collections(self):
        payload = make_payload(platform="xiaohongshu")
        payload["followers_raw"] = "1万"
        payload["recent_posts"][2]["likes_raw"] = "4500"
        payload["recent_posts"][2]["collects_raw"] = "15500"
        for index, post in enumerate(payload["recent_posts"]):
            if index != 2:
                post["likes_raw"] = "1000"
                post["collects_raw"] = "1000"
        result = self.module.scan(payload)
        candidate = result["results"][2]

        self.assertEqual(candidate["grade"], "现象级")
        self.assertEqual(candidate["R"], 10.0)
        self.assertEqual(candidate["url"], "https://www.xiaohongshu.com/explore/post-2")

    def test_result_is_json_serializable_with_complete_scan_gate(self):
        restored = json.loads(json.dumps(self.module.scan(make_payload()), ensure_ascii=False))
        self.assertEqual(restored["schema_version"], 1)
        self.assertEqual(restored["platform"], "douyin")
        self.assertIn("excluded", restored)
        self.assertTrue(restored["requires_user_selection_for_deep_process"])

    def test_rejects_post_id_that_cannot_form_a_safe_canonical_url(self):
        payload = make_payload()
        payload["recent_posts"][0]["post_id"] = "../escape"
        with self.assertRaises(ValueError):
            self.module.scan(payload)


if __name__ == "__main__":
    unittest.main()
