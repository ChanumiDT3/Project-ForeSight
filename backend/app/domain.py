"""Pure decided validation and scoring rules."""
from decimal import Decimal, localcontext
from app.core import AppError


# PUBLIC_INTERFACE
def plain(value: Decimal) -> str:
    """Render a decimal in positional notation without rounding (never "1E+1" or "-0")."""
    if value.is_zero():
        value = value.copy_abs()
    return format(value, "f")


# PUBLIC_INTERFACE
def validate_value(value: Decimal, minimum, maximum, precision: int, unit: str):
    """Enforce inclusive range and numeric decimal precision without rounding input."""
    if not value.is_finite():
        raise AppError(422, "invalid_value", "A finite numeric value is required")
    if value < Decimal(minimum) or value > Decimal(maximum):
        raise AppError(422, "invalid_value", f"Valid range: {minimum} to {maximum} {unit}")
    # Compare normalized exponent rather than literal trailing zeroes.
    with localcontext() as context:
        context.prec = max(28, len(value.as_tuple().digits) + 4)
        if value.normalize().as_tuple().exponent < -precision:
            raise AppError(422, "invalid_precision", f"At most {precision} decimal places")


# PUBLIC_INTERFACE
def score(value: Decimal, threshold: Decimal, criticality: int, bands: list):
    """Calculate exact score bands by cross multiplication, never rounded percent.

    The returned percentage is unrounded; display rounding is held (CM-Q2).
    """
    delta = (value - threshold) * 100
    exceedance_score = 1 if delta <= threshold * Decimal(bands[0]) else (
        2 if delta <= threshold * Decimal(bands[1]) else 3)
    with localcontext() as context:
        context.prec = 50
        percent = plain(delta / threshold)
    return {
        "exceedance_percent": percent,
        "exceedance_score": exceedance_score,
        "criticality": criticality,
        "priority_score": criticality + exceedance_score,
    }
