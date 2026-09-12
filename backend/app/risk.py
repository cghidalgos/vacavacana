"""Línea base heurística, equivalente a lib/risk-engine.ts del frontend."""

from typing import Iterable, List

from . import models


def assess_risk(cow: "models.Cow") -> dict:
    score = max(0, min(100, round((cow.interval_months / 18) * 100)))
    if cow.interval_months >= 14:
        level = "Alto"
    elif cow.interval_months >= 12:
        level = "Medio"
    else:
        level = "Bajo"

    reasons: List[str] = []
    if cow.interval_months >= 14:
        reasons.append(f"Intervalo actual de {cow.interval_months:.1f} meses")
    elif cow.interval_months >= 12:
        reasons.append(f"Intervalo cercano al umbral: {cow.interval_months:.1f} meses")
    if cow.body_condition < 2.75:
        reasons.append(f"Condición corporal baja ({cow.body_condition:.1f}/5)")
    if cow.health_events > 1:
        reasons.append(f"{cow.health_events} eventos sanitarios recientes")
    if cow.milk_liters > 28:
        reasons.append("Producción alta que puede requerir seguimiento")
    if not reasons:
        reasons.append("Sin señales de riesgo destacadas")

    if level == "Alto":
        action = "Revisar ficha y priorizar seguimiento"
    elif level == "Medio":
        action = "Programar revisión de rutina"
    else:
        action = "Continuar monitoreo"

    return {"level": level, "score": score, "reasons": reasons, "action": action}


def summarize(cows: Iterable["models.Cow"]) -> dict:
    cows = list(cows)
    levels = [assess_risk(cow)["level"] for cow in cows]
    total = len(cows)
    return {
        "total": total,
        "high": levels.count("Alto"),
        "medium": levels.count("Medio"),
        "low": levels.count("Bajo"),
        "average_interval": sum(c.interval_months for c in cows) / total if total else 0.0,
        "average_milk": sum(c.milk_liters for c in cows) / total if total else 0.0,
    }
