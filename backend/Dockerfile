# El contexto de build es la raíz del repositorio (así el modelo entrenado de
# modelo/ entra en la imagen). Ver docker-compose.yml y render.yaml.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    RUTA_MODELO=/modelo/modelo_clasificacion_reproductiva.joblib

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY modelo/modelo_clasificacion_reproductiva.joblib /modelo/

EXPOSE 8000

# Render inyecta PORT; en local se usa 8000. En desarrollo docker-compose
# sobrescribe este comando para activar --reload.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
