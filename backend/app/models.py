from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Cow(Base):
    __tablename__ = "cows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ear_tag: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    breed: Mapped[str] = mapped_column(String(60), default="")
    birth_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(30), default="Activa")
    parity: Mapped[int] = mapped_column(Integer, default=0)
    last_calving: Mapped[str] = mapped_column(String(20), default="")
    last_service: Mapped[str] = mapped_column(String(20), default="")
    gestation_days: Mapped[int] = mapped_column(Integer, default=0)
    interval_months: Mapped[float] = mapped_column(Float, default=0.0)
    milk_liters: Mapped[float] = mapped_column(Float, default=0.0)
    body_condition: Mapped[float] = mapped_column(Float, default=0.0)
    health_events: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
