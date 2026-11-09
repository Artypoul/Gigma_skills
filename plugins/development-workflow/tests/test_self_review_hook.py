"""Exercise the optional Stop helper without registering a runtime hook."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/self-review-report/scripts/short-task-stop.ps1"
)
PWSH = shutil.which("pwsh")
PENDING = "Второй проход: запланирован (короткая задача)."


@unittest.skipUnless(PWSH, "PowerShell 7 is required to execute the optional helper")
class SelfReviewHookTests(unittest.TestCase):
    def invoke(self, payload):
        result = subprocess.run(
            [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT)],
            input=payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
            capture_output=True,
            check=True,
            timeout=15,
        )
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def event(self, **overrides):
        return {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Проверено.\n" + PENDING,
            **overrides,
        }

    def test_explicit_pending_line_requests_one_continuation(self):
        for ending in ("", "\n  "):
            with self.subTest(ending=repr(ending)):
                result = self.invoke(self.event(last_assistant_message=PENDING + ending))
                self.assertEqual(result["decision"], "block")
                self.assertTrue(result["reason"].strip())

    def test_recursive_or_invalid_events_do_not_request_work(self):
        events = [
            self.event(stop_hook_active=True),
            self.event(hook_event_name="Interrupt"),
            self.event(stop_hook_active="false"),
            {"hook_event_name": "Stop", "last_assistant_message": PENDING},
            self.event(last_assistant_message=None),
            "{",
        ]
        for event in events:
            with self.subTest(event=event):
                self.assertEqual(self.invoke(event), {})

    def test_normal_answer_or_nonfinal_marker_does_not_request_work(self):
        for text in ("Готово.", PENDING + "\nЕщё текст", "Цитата: " + PENDING):
            with self.subTest(text=text):
                self.assertEqual(self.invoke(self.event(last_assistant_message=text)), {})


if __name__ == "__main__":
    unittest.main()
