"""Carga inicial con el rodeo demo (mismos registros que lib/demo-data.ts)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Cow

DEMO_COWS = [
    dict(ear_tag="BOV-001", breed="Holstein", birth_date="2020-03-18", status="En observación", parity=3, last_calving="2024-01-08", last_service="2024-04-06", gestation_days=0, interval_months=14.2, milk_liters=31.5, body_condition=2.5, health_events=2, notes="Repetición de servicio registrada.", demo=True),
    dict(ear_tag="BOV-002", breed="Jersey", birth_date="2019-08-02", status="Activa", parity=4, last_calving="2024-04-21", last_service="2024-07-18", gestation_days=0, interval_months=11.8, milk_liters=22.4, body_condition=3.1, health_events=0, notes="Comportamiento reproductivo estable.", demo=True),
    dict(ear_tag="BOV-003", breed="Pardo Suizo", birth_date="2021-01-27", status="Seca", parity=2, last_calving="2024-02-14", last_service="2024-06-08", gestation_days=0, interval_months=13.1, milk_liters=18.6, body_condition=2.9, health_events=1, notes="Pendiente de confirmación de gestación.", demo=True),
    dict(ear_tag="BOV-004", breed="Holstein", birth_date="2020-11-12", status="Activa", parity=2, last_calving="2024-06-02", last_service="2024-08-22", gestation_days=0, interval_months=8.7, milk_liters=28.2, body_condition=3.4, health_events=0, notes="", demo=True),
    dict(ear_tag="BOV-005", breed="Jersey", birth_date="2018-05-30", status="En observación", parity=5, last_calving="2023-12-11", last_service="2024-04-28", gestation_days=0, interval_months=15.6, milk_liters=19.8, body_condition=2.4, health_events=3, notes="Seguimiento por condición corporal.", demo=True),
    dict(ear_tag="BOV-006", breed="Holstein", birth_date="2022-02-19", status="Activa", parity=1, last_calving="2024-06-19", last_service="2024-09-01", gestation_days=0, interval_months=7.4, milk_liters=25.1, body_condition=3.3, health_events=0, notes="", demo=True),
]


def seed_if_empty(db: Session) -> int:
    """Inserta el rodeo demo solo si la tabla está vacía. Devuelve cuántas creó."""
    if db.scalar(select(Cow).limit(1)) is not None:
        return 0
    db.add_all(Cow(**data) for data in DEMO_COWS)
    db.commit()
    return len(DEMO_COWS)
