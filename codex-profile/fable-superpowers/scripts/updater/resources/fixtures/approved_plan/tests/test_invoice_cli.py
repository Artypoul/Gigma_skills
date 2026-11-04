import unittest

from invoice_cli import format_total


class FormatTotalTests(unittest.TestCase):
    def test_fixed_decimal_format(self):
        self.assertEqual(format_total(4), "4.00")


if __name__ == "__main__":
    unittest.main()
