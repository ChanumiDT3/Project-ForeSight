"""Pydantic boundary validation; state-dependent checks live in services."""
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Nonblank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Quantity = Annotated[int, Field(strict=True, ge=1)]


# PUBLIC_INTERFACE
class Input(BaseModel):
    """Reject unknown request fields rather than silently ignoring client input."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# PUBLIC_INTERFACE
class ParameterInput(Input):
    """Maximum-only parameter registration input."""

    kind: Literal["temperature", "vibration", "cycle_count", "runtime_hours", "custom"]
    name: Nonblank
    threshold: Decimal = Field(gt=0)
    threshold_type: Literal["max"] = "max"
    suggested_action: str = ""
    unit: Nonblank | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    precision: int | None = Field(default=None, strict=True, ge=0)
    cumulative: bool | None = None


# PUBLIC_INTERFACE
class MachineInput(Input):
    """Machine registration input, allowing zero initial parameters."""

    equipment_id: Nonblank
    name: Nonblank
    location: Nonblank
    equipment_type: Nonblank
    criticality: int = Field(strict=True, ge=1, le=3)
    parameters: list[ParameterInput] = Field(default_factory=list)
    baseline: Decimal | None = None
    current_meter: Decimal | None = None


# PUBLIC_INTERFACE
class NewParameterInput(ParameterInput):
    """Parameter input when adding monitoring after machine registration."""

    baseline: Decimal | None = None
    current_meter: Decimal | None = None


# PUBLIC_INTERFACE
class CumulativeInput(Input):
    """Mutable-before-reading configuration of a custom cumulative stream."""

    cumulative: bool


# PUBLIC_INTERFACE
class ReadingInput(Input):
    """One immutable measured value for one configured parameter."""

    parameter_id: Nonblank
    value: Decimal


# PUBLIC_INTERFACE
class CriticalityInput(Input):
    """Future-only machine criticality adjustment."""

    criticality: int = Field(strict=True, ge=1, le=3)


# PUBLIC_INTERFACE
class EquipmentDetailsInput(Input):
    """Editable descriptive machine fields."""

    name: Nonblank
    location: Nonblank
    equipment_type: Nonblank


# PUBLIC_INTERFACE
class SuggestedActionInput(Input):
    """Editable future-alert guidance."""

    suggested_action: str


# PUBLIC_INTERFACE
class ThresholdInput(Input):
    """Positive safe maximum for future evaluation."""

    threshold: Decimal = Field(gt=0)


# PUBLIC_INTERFACE
class ReasonInput(Input):
    """Required reason for dismissal or cancellation."""

    reason: Nonblank


# PUBLIC_INTERFACE
class WorkOrderEditInput(Input):
    """Partial work-order assignment, due date, and service flag update."""

    assignee: Nonblank | None = None
    due_at: AwareDatetime | None = None
    scheduled_service: bool | None = None


# PUBLIC_INTERFACE
class ChecklistItemInput(Input):
    """One planned work-order part."""

    part_name: Nonblank
    part_number: str | None = None
    quantity: Quantity
    availability: Literal["yes", "no", "ordered"]
    notes: str | None = None


# PUBLIC_INTERFACE
class PartsChecklistInput(Input):
    """Complete replacement of an optional parts checklist."""

    items: list[ChecklistItemInput] = Field(default_factory=list)


# PUBLIC_INTERFACE
class PartUsedInput(Input):
    """One part recorded as actually used during closure."""

    part_name: Nonblank
    part_number: str | None = None
    quantity: Quantity
    notes: str | None = None


# PUBLIC_INTERFACE
class ClosureInput(Input):
    """Closure data, including runtime reset input where it applies."""

    resolution_note: str = ""
    parts_used: list[PartUsedInput] = Field(default_factory=list)
    no_parts_used: bool = False
    hour_meter_value: Decimal | None = None


# PUBLIC_INTERFACE
class AddendumInput(Input):
    """Insert-only note after work-order closure."""

    note: Nonblank


# PUBLIC_INTERFACE
class Result(BaseModel):
    """Standard resource or command result envelope."""

    data: dict


# PUBLIC_INTERFACE
class Page(BaseModel):
    """Standard bounded collection response envelope."""

    data: list[dict]
    total: int
    offset: int
    limit: int


# PUBLIC_INTERFACE
class Problem(BaseModel):
    """RFC 9457-style problem detail response."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    correlation_id: str
