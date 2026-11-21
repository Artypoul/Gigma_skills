"""Verify that handoff guidance never waives mandatory acceptance gates."""
from pathlib import Path
import unittest


SKILL = Path(__file__).resolve().parents[1] / 'skills' / 'development-handoff' / 'SKILL.md'


class HandoffReadinessPolicyTests(unittest.TestCase):
    def test_ready_with_risk_is_for_optional_risks_only(self):
        content = SKILL.read_text(encoding='utf-8')
        section = content.split('## Prod-Ready Gate\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn(
            'If any mandatory criterion is failed, blocked, unknown, incomplete, or unverified, '
            'answer `not ready yet` and name the missing evidence.',
            section)
        self.assertIn(
            '`ready with this explicit risk` is allowed only for optional residual risks '
            'after every mandatory criterion has current passing evidence.',
            section)
        self.assertNotIn(
            'If any item is unknown, answer "not ready yet" or '
            '"ready with this explicit risk".',
            section)


if __name__ == '__main__':
    unittest.main()
