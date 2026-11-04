def apply_discount(amount, percent):
    """Return the amount after a percentage discount between 0 and 100."""
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    if percent == 100:
        return 0.0
    return amount - percent
