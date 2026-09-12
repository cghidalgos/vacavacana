from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

RiskLevel = Literal["Bajo", "Medio", "Alto"]
CowStatus = Literal["Activa", "Seca", "En observación"]


def to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class CowBase(CamelModel):
    ear_tag: str = Field(min_length=1, max_length=40)
    breed: str = ""
    birth_date: str = ""
    status: CowStatus = "Activa"
    parity: int = 0
    last_calving: str = ""
    last_service: str = ""
    gestation_days: int = 0
    interval_months: float = 0.0
    milk_liters: float = 0.0
    body_condition: float = 0.0
    health_events: int = 0
    notes: str = ""
    demo: bool = False


class CowCreate(CowBase):
    pass


class CowUpdate(CamelModel):
    ear_tag: Optional[str] = None
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    status: Optional[CowStatus] = None
    parity: Optional[int] = None
    last_calving: Optional[str] = None
    last_service: Optional[str] = None
    gestation_days: Optional[int] = None
    interval_months: Optional[float] = None
    milk_liters: Optional[float] = None
    body_condition: Optional[float] = None
    health_events: Optional[int] = None
    notes: Optional[str] = None
    demo: Optional[bool] = None


class RiskAssessment(CamelModel):
    level: RiskLevel
    score: int
    reasons: List[str]
    action: str


class CowOut(CowBase):
    # El frontend usa id como string.
    id: str
    risk: RiskAssessment

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, value: object) -> str:
        return str(value)


class Summary(CamelModel):
    total: int
    high: int
    medium: int
    low: int
    average_interval: float
    average_milk: float


class ImportResult(CamelModel):
    created: int
    updated: int
    skipped: int
    errors: List[str]
