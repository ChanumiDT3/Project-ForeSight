"""Pydantic boundary validation; state-dependent checks live in services."""
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Nonblank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# PUBLIC_INTERFACE
class Input(BaseModel):
    """Reject unknown fields to avoid silent input loss."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# PUBLIC_INTERFACE
class ParameterInput(Input):
    """Maximum-only parameter definition; custom cumulative semantics stay held."""
    kind: Literal["temperature", "vibration", "cycle_count", "runtime_hours", "custom"] = Field(description="Parameter family")
    name: Nonblank = Field(description="Display name")
    threshold: Decimal = Field(gt=0, description="Positive inclusive-range maximum safe limit")
    threshold_type: Literal["max"] = Field(default="max", description="Only supported comparison")
    suggested_action: str = Field(default="", description="Free text; blank uses machine-name fallback")
    unit: Nonblank | None = Field(default=None, description="Required for custom parameters")
    minimum: Decimal | None = Field(default=None, description="Custom inclusive valid minimum")
    maximum: Decimal | None = Field(default=None, description="Custom inclusive valid maximum")
    precision: int | None = Field(default=None, strict=True, ge=0, description="Custom decimal places")


# PUBLIC_INTERFACE
class MachineInput(Input):
    """Equipment registration; current meter is captured but not made a reading."""
    equipment_id: Nonblank = Field(description="Plant-unique equipment identifier")
    name: Nonblank = Field(description="Machine name")
    location: Nonblank = Field(description="Plant location")
    equipment_type: Nonblank = Field(description="Equipment type")
    criticality: int = Field(strict=True, ge=1, le=3, description="Must be 1, 2, or 3")
    parameters: list[ParameterInput] = Field(description="Configured health parameters")
    baseline: Decimal | None = Field(default=None, description="Runtime meter at last service")
    current_meter: Decimal | None = Field(default=None, description="Runtime registration meter, not a saved reading")


# PUBLIC_INTERFACE
class ReadingInput(Input):
    """Exactly one value, with no client timestamp or derived counter."""
    parameter_id: Nonblank = Field(description="Configured parameter UUID")
    value: Decimal = Field(description="Measured numeric value")


# PUBLIC_INTERFACE
class CriticalityInput(Input):
    """A criticality edit changes future evaluation only."""
    criticality: int = Field(strict=True, ge=1, le=3, description="Must be 1, 2, or 3")


# PUBLIC_INTERFACE
class EquipmentDetailsInput(Input):
    """Editable descriptive equipment fields, without baseline replacement."""
    name: Nonblank = Field(description="Machine display name")
    location: Nonblank = Field(description="Plant location")
    equipment_type: Nonblank = Field(description="Equipment type")


# PUBLIC_INTERFACE
class SuggestedActionInput(Input):
    """Editable parameter guidance; blank text uses the alert fallback."""
    suggested_action: str = Field(description="Engineer-entered action text")


# PUBLIC_INTERFACE
class ThresholdInput(Input):
    """Threshold edit for future readings only."""
    threshold: Decimal = Field(gt=0, description="Positive inclusive-range safe maximum")


# PUBLIC_INTERFACE
class ReasonInput(Input):
    """Required free-text dismissal or cancellation reason."""
    reason: Nonblank = Field(description="Nonblank reason; no invented maximum length")


# PUBLIC_INTERFACE
class Result(BaseModel):
    """Standard single-result envelope."""
    data: dict = Field(description="Resource or command result")


# PUBLIC_INTERFACE
class Page(BaseModel):
    """Standard bounded collection response."""
    data: list[dict] = Field(description="Requested page")
    total: int = Field(description="Total matching records")
    offset: int = Field(description="Zero-based offset")
    limit: int = Field(description="Maximum returned items")


# PUBLIC_INTERFACE
class Problem(BaseModel):
    """RFC 9457 problem details with correlation identifier."""
    type: str = Field(description="Stable problem URN")
    title: str = Field(description="Machine-readable failure code")
    status: int = Field(description="HTTP status")
    detail: str = Field(description="Safe diagnostic explanation")
    instance: str = Field(description="Request path")
    correlation_id: str = Field(description="Server-generated support identifier")
