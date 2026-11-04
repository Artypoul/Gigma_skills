import unittest

from discounts import apply_discount


class DiscountTests(unittest.TestCase):
    def test_ten_percent_of_one_hundred(self):
        self.assertEqual(apply_discount(100, 10), 90)

    def test_zero_percent_preserves_amount(self):
        self.assertEqual(apply_discount(200, 0), 200)

    def test_full_discount_returns_zero(self):
        self.assertEqual(apply_discount(200, 100), 0)

    def test_zero_amount_without_discount(self):
        self.assertEqual(apply_discount(0, 0), 0)

    def test_invalid_percentage_is_rejected(self):
        for percent in (-1, 101):
            with self.subTest(percent=percent):
                with self.assertRaises(ValueError):
                    apply_discount(100, percent)


if __name__ == "__main__":
    unittest.main()
