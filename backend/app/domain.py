"""Pure validation, scoring, and configured calendar rules."""
from datetime import datetime, timedelta
from decimal import Decimal, localcontext

from app.core import AppError, to_utc_text


# PUBLIC_INTERFACE
def plain(value: Decimal) -> str:
    """Render a decimal without exponent notation or negative zero."""
    if value.is_zero():
        value = value.copy_abs()
    return format(value, "f")


# PUBLIC_INTERFACE
def validate_value(value: Decimal, minimum, maximum, precision: int, unit: str):
    """Enforce an inclusive valid range and decimal precision."""
    if not value.is_finite():
        raise AppError(422, "invalid_value", "A finite numeric value is required")
    if value < Decimal(minimum) or value > Decimal(maximum):
        raise AppError(422, "invalid_value", f"Valid range: {minimum} to {maximum} {unit}")
    with localcontext() as context:
        context.prec = max(28, len(value.as_tuple().digits) + 4)
        if value.normalize().as_tuple().exponent < -precision:
            raise AppError(422, "invalid_precision", f"At most {precision} decimal places")


# PUBLIC_INTERFACE
def score(value: Decimal, threshold: Decimal, criticality: int, bands: list):
    """Calculate exact priority bands without rounding the comparison value."""
    delta = (value - threshold) * 100
    exceedance_score = (
        1
        if delta <= threshold * Decimal(bands[0])
        else 2
        if delta <= threshold * Decimal(bands[1])
        else 3
    )
    with localcontext() as context:
        context.prec = 50
        percent = plain(delta / threshold)
    return {
        "exceedance_percent": percent,
        "exceedance_score": exceedance_score,
        "criticality": criticality,
        "priority_score": criticality + exceedance_score,
    }


# PUBLIC_INTERFACE
def priority_label(priority_score: int, rules: dict) -> str:
    """Resolve a stored priority score to its configured display label."""
    label = rules["priority_labels"].get(str(priority_score))
    if label is None:
        raise AppError(500, "priority_unmapped", "Stored priority score has no configured label")
    return label


# PUBLIC_INTERFACE
def default_due_at(created: datetime, label: str, rules: dict) -> str:
    """Return the configured calendar-day default due time."""
    return to_utc_text(created + timedelta(days=int(rules["due_days"][label])))
