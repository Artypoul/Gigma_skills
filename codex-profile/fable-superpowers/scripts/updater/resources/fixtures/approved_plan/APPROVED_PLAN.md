# Invoice currency formatting implementation plan

Status: approved by the user. The behavior and interfaces below are settled.
Chosen execution method: Superpowers `executing-plans`, in the current checkout.

## Goal

Add currency normalization and a formatted invoice line while preserving the
existing `invoice_total` and `format_total` interfaces.

## Constraints

- Use Python's standard library only. Do not add dependencies or network calls.
- Use the current small module structure and the existing unittest suite.
- A currency code is exactly three ASCII letters after trimming surrounding
  whitespace. Return the uppercase code. Reject all other values with ValueError.
- Existing prices are numeric values. Do not add unrelated price validation,
  currency conversion, localization, new command-line arguments, or persistence.

## Task 1: Normalize currency codes

Files: `invoice_helpers.py`, `tests/test_invoice_helpers.py`.

Interface: `normalize_currency(currency: str) -> str`.

- [ ] Add focused tests for `" usd " -> "USD"`, `"eur" -> "EUR"`,
  `"GBP" -> "GBP"`, and rejection of `""`, `"US"`, `"USDD"`, `"12x"`,
  and non-ASCII `"éur"`.
- [ ] Run the focused tests to confirm the new behavior is missing.
- [ ] Implement the helper without changing `invoice_total(prices)`.
- [ ] Run the focused tests and the existing tests.

## Task 2: Format complete invoice lines

Files: `invoice_cli.py`, `tests/test_invoice_cli.py`.

Interface: `format_invoice(prices, currency: str) -> str`.
Consumes: `invoice_helpers.invoice_total` and `invoice_helpers.normalize_currency`.

- [ ] Add tests for `format_invoice([1.25, 2.75], " usd ") == "USD 4.00"`,
  `format_invoice([], "eur") == "EUR 0.00"`, and rejection of `"US"`.
- [ ] Run the focused tests to confirm the new behavior is missing.
- [ ] Implement formatting as the normalized currency code, one space, and the
  existing two-decimal amount format. Preserve `format_total(amount)`.
- [ ] Run the complete suite and review the resulting diff against this plan.

## Final validation

`python -m unittest discover -s tests -v`

The result is complete when both interfaces work as specified, the original
interfaces still work, and the complete suite passes. No remote publication is
part of this task.
