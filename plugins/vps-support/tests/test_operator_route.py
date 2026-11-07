"""Check the operator instructions that a VPS skill reader can actually reach."""
from pathlib import Path
import unittest


SKILLS = Path(__file__).resolve().parents[1] / "skills"
NODE = "../vps-node-panel-setup/SKILL.md#jolymmiles"
PANEL = "../vps-panel-setup/SKILL.md#profile-verification"


class OperatorRouteTests(unittest.TestCase):
    def follow_section(self, source, text, target):
        self.assertIn(f"]({target})", text, f"Missing route from {source.parent.name}")
        filename, anchor = target.split("#")
        path = (source.parent / filename).resolve()
        contents = path.read_text(encoding="utf-8")
        marker = f'<a id="{anchor}"></a>'
        self.assertEqual(contents.count(marker), 1, f"Missing or ambiguous section: {target}")
        section = contents.split(marker, 1)[1].lstrip()
        self.assertTrue(section.startswith("## "), f"Expected a section at {target}")
        return path, section.split("\n## ", 1)[0]

    def test_operator_can_discover_and_follow_the_verification_method(self):
        entry = SKILLS / "vps-support/SKILL.md"
        entry_text = entry.read_text(encoding="utf-8")
        self.assertRegex(entry_text.split("---", 2)[1], r"(?mi)^description:.*примени VPS")
        node, method = self.follow_section(entry, entry_text, NODE)
        frontmatter = node.read_text(encoding="utf-8").split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?mi)^description:.*Jolymmiles")
        for evidence in ("/proc/<PID>/exe", "SHA-256", "Jolymmiles/Xray-core/issues",
                         "Jolymmiles/Xray-core/pulls", "тем же клиентом", "run -test"):
            with self.subTest(method=evidence):
                self.assertIn(evidence, method)
        _, acceptance = self.follow_section(node, method, PANEL)
        # These conditions must apply to the same acceptance step.
        step = next((line for line in acceptance.splitlines()
                     if "каждый затронутый транспорт" in line), "")
        for condition in ("из подписки", "вне целевой ноды", "результат запроса через профиль",
                          "partial"):
            with self.subTest(acceptance=condition):
                self.assertIn(condition, step)


if __name__ == "__main__":
    unittest.main()
