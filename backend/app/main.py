import csv
import io
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import chat, models, prediccion, schemas
from .database import Base, SessionLocal, engine, get_db
from .risk import assess_risk, summarize
from .seed import seed_if_empty

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    yield


app = FastAPI(title="CampoClaro API", version="1.0.0", lifespan=lifespan)

app.include_router(chat.router)
app.include_router(prediccion.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_out(cow: models.Cow) -> schemas.CowOut:
    return schemas.CowOut.model_validate(
        {
            **{c.name: getattr(cow, c.name) for c in models.Cow.__table__.columns},
            "risk": assess_risk(cow),
        }
    )


def get_cow_or_404(db: Session, cow_id: int) -> models.Cow:
    cow = db.get(models.Cow, cow_id)
    if cow is None:
        raise HTTPException(status_code=404, detail="Vaca no encontrada")
    return cow


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/cows", response_model=List[schemas.CowOut])
def list_cows(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Filtra por caravana"),
    level: Optional[schemas.RiskLevel] = Query(None, description="Filtra por nivel de riesgo"),
):
    stmt = select(models.Cow).order_by(models.Cow.ear_tag)
    if search:
        stmt = stmt.where(models.Cow.ear_tag.ilike(f"%{search}%"))
    cows = db.scalars(stmt).all()
    if level:
        cows = [c for c in cows if assess_risk(c)["level"] == level]
    return [to_out(c) for c in cows]


@app.get("/api/cows/{cow_id}", response_model=schemas.CowOut)
def get_cow(cow_id: int, db: Session = Depends(get_db)):
    return to_out(get_cow_or_404(db, cow_id))


@app.post("/api/cows", response_model=schemas.CowOut, status_code=201)
def create_cow(payload: schemas.CowCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(models.Cow).where(models.Cow.ear_tag == payload.ear_tag))
    if exists:
        raise HTTPException(status_code=409, detail="Ya existe una vaca con esa caravana")
    cow = models.Cow(**payload.model_dump())
    db.add(cow)
    db.commit()
    db.refresh(cow)
    return to_out(cow)


@app.patch("/api/cows/{cow_id}", response_model=schemas.CowOut)
def update_cow(cow_id: int, payload: schemas.CowUpdate, db: Session = Depends(get_db)):
    cow = get_cow_or_404(db, cow_id)
    changes = payload.model_dump(exclude_unset=True)
    if "ear_tag" in changes:
        clash = db.scalar(
            select(models.Cow).where(
                models.Cow.ear_tag == changes["ear_tag"], models.Cow.id != cow_id
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail="Ya existe una vaca con esa caravana")
    for field, value in changes.items():
        setattr(cow, field, value)
    db.commit()
    db.refresh(cow)
    return to_out(cow)


@app.delete("/api/cows/{cow_id}", status_code=204)
def delete_cow(cow_id: int, db: Session = Depends(get_db)):
    db.delete(get_cow_or_404(db, cow_id))
    db.commit()


@app.get("/api/summary", response_model=schemas.Summary)
def get_summary(db: Session = Depends(get_db)):
    return schemas.Summary.model_validate(summarize(db.scalars(select(models.Cow)).all()))


@app.get("/api/cows/{cow_id}/risk", response_model=schemas.RiskAssessment)
def get_risk(cow_id: int, db: Session = Depends(get_db)):
    return schemas.RiskAssessment.model_validate(assess_risk(get_cow_or_404(db, cow_id)))


CSV_HEADER = [
    "caravana", "raza", "fecha_nacimiento", "estado", "paridad",
    "ultimo_parto", "ultimo_servicio", "dias_gestacion", "intervalo_meses",
    "produccion_litros", "condicion_corporal", "eventos_sanitarios", "notas",
]

CSV_TO_FIELD = dict(zip(CSV_HEADER, [
    "ear_tag", "breed", "birth_date", "status", "parity",
    "last_calving", "last_service", "gestation_days", "interval_months",
    "milk_liters", "body_condition", "health_events", "notes",
]))


@app.get("/api/export.csv")
def export_csv(db: Session = Depends(get_db)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id"] + CSV_HEADER + ["riesgo", "score"])
    for cow in db.scalars(select(models.Cow).order_by(models.Cow.ear_tag)):
        risk = assess_risk(cow)
        writer.writerow(
            [cow.id]
            + [getattr(cow, CSV_TO_FIELD[h]) for h in CSV_HEADER]
            + [risk["level"], risk["score"]]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="campoclaro-vacas.csv"'},
    )


@app.post("/api/import", response_model=schemas.ImportResult)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa un CSV con los encabezados de /api/export.csv. Actualiza por caravana."""
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "caravana" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="El CSV debe incluir la columna 'caravana'")

    created = updated = skipped = 0
    errors: List[str] = []

    for line, row in enumerate(reader, start=2):
        ear_tag = (row.get("caravana") or "").strip()
        if not ear_tag:
            skipped += 1
            errors.append(f"Fila {line}: caravana vacía")
            continue

        values = {}
        try:
            for header, field in CSV_TO_FIELD.items():
                if header not in row or row[header] is None or row[header] == "":
                    continue
                column = models.Cow.__table__.columns[field]
                text = row[header].strip()
                python_type = column.type.python_type
                values[field] = python_type(text) if python_type is not str else text
        except (ValueError, TypeError) as exc:
            skipped += 1
            errors.append(f"Fila {line}: valor inválido ({exc})")
            continue

        cow = db.scalar(select(models.Cow).where(models.Cow.ear_tag == ear_tag))
        if cow:
            for field, value in values.items():
                setattr(cow, field, value)
            updated += 1
        else:
            db.add(models.Cow(**values))
            created += 1

    db.commit()
    return schemas.ImportResult.model_validate(
        {"created": created, "updated": updated, "skipped": skipped, "errors": errors[:20]}
    )
