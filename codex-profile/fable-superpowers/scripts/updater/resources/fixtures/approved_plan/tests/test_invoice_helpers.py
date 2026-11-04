import unittest

from invoice_helpers import invoice_total


class InvoiceTotalTests(unittest.TestCase):
    def test_total(self):
        self.assertEqual(invoice_total([1.25, 2.75]), 4)

    def test_empty_invoice(self):
        self.assertEqual(invoice_total([]), 0)


if __name__ == "__main__":
    unittest.main()
