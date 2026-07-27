import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_keyframes.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class ExtractKeyframesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()
        self.media = self.root / "short.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=160x90:rate=10",
                "-t",
                "1.5",
                "-pix_fmt",
                "yuv420p",
                "-y",
                str(self.media),
            ],
            check=True,
            timeout=30,
        )
        self.transcript = self.run_dir / "final-transcript.md"
        self.transcript.write_text("有效逐字稿", encoding="utf-8")
        self.summary = self.run_dir / "run-summary.json"
        self.summary.write_text(
            json.dumps(
                {
                    "runDir": str(self.run_dir),
                    "mediaInput": str(self.media),
                    "finalTranscriptTarget": str(self.transcript),
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self):
        return subprocess.run(
            ["python3", str(SCRIPT), "--run-summary", str(self.summary)],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_extracts_three_frames_and_clamps_short_video(self):
        completed = self.run_script()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)

        self.assertEqual([frame["requested_seconds"] for frame in result["frames"]], [0, 2, 5])
        self.assertFalse(result["frames"][0]["clamped"])
        self.assertTrue(result["frames"][1]["clamped"])
        self.assertTrue(result["frames"][2]["clamped"])
        for frame in result["frames"]:
            path = Path(frame["path"])
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent.resolve(), (self.run_dir / "keyframes").resolve())

    def test_requires_completed_transcript(self):
        self.transcript.unlink()
        completed = self.run_script()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("transcript", completed.stderr.lower())

    def test_rejects_symlinked_keyframe_directory(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.run_dir / "keyframes").symlink_to(outside, target_is_directory=True)
        completed = self.run_script()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("keyframes", completed.stderr.lower())
        self.assertEqual(list(outside.iterdir()), [])

    def test_rejects_run_dir_that_does_not_own_summary(self):
        outside = self.root / "outside"
        outside.mkdir()
        payload = json.loads(self.summary.read_text(encoding="utf-8"))
        payload["runDir"] = str(outside)
        self.summary.write_text(json.dumps(payload), encoding="utf-8")
        completed = self.run_script()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("run-summary", completed.stderr.lower())
        self.assertFalse((outside / "keyframes").exists())


if __name__ == "__main__":
    unittest.main()
