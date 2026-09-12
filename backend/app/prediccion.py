"""Endpoint de predicción: sirve el modelo entrenado en modelo/.

El artefacto .joblib es autodescriptivo — lleva el pipeline con su preprocesado y los
metadatos de qué acepta cada campo — así que este módulo no necesita saber nada del
CSV de entrenamiento ni repetir las listas de opciones.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .schemas import CamelModel

router = APIRouter(prefix="/api/prediccion", tags=["modelo"])

RUTA_MODELO = Path(
    os.getenv("RUTA_MODELO", "/modelo/modelo_clasificacion_reproductiva.joblib")
)

# Orden de peor a mejor: sirve para pintar el resultado y ordenar las probabilidades.
ORDEN_CLASES = ["Mala", "Regular", "Buena", "Excelente"]


@lru_cache(maxsize=1)
def _artefacto() -> Dict[str, Any]:
    """Carga el modelo una vez y lo deja en memoria entre peticiones."""
    if not RUTA_MODELO.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No se encontró el modelo en {RUTA_MODELO}. Ejecuta "
                "modelo/modelo_clasificacion.ipynb para generarlo."
            ),
        )
    try:
        return joblib.load(RUTA_MODELO)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo cargar el modelo: {exc}")


class CampoNumerico(CamelModel):
    nombre: str
    etiqueta: str
    minimo: float
    maximo: float
    sugerido: float
    entero: bool
    unidad: Optional[str] = None


class CampoOpciones(CamelModel):
    nombre: str
    etiqueta: str
    opciones: List[str]


class Esquema(CamelModel):
    """Lo que el formulario necesita para construirse solo."""

    objetivo: str
    clases: List[str]
    modelo: str
    f1_macro: float
    entrenado_con: int
    fecha: str
    numericos: List[CampoNumerico]
    booleanos: List[CampoOpciones]
    categoricos: List[CampoOpciones]


class Probabilidad(CamelModel):
    clase: str
    probabilidad: float


class Resultado(CamelModel):
    prediccion: str
    confianza: float
    probabilidades: List[Probabilidad]
    aviso: Optional[str] = None


# Etiquetas y unidades legibles: el modelo trae nombres de columna, no texto de interfaz.
ETIQUETAS = {
    "edad_meses": ("Edad", "meses"),
    "peso_kg": ("Peso", "kg"),
    "condicion_corporal": ("Condición corporal", "de 1 a 5"),
    "edad_primer_parto_meses": ("Edad al primer parto", "meses"),
    "num_partos": ("Número de partos", None),
    "intervalo_partos_meses": ("Intervalo entre partos", "meses"),
    "meses_desde_ultimo_parto": ("Meses desde el último parto", "meses"),
    "produccion_leche_lt_dia": ("Producción de leche", "litros/día"),
    "cachona": ("¿Es cachona?", None),
    "perdida_cria": ("¿Ha perdido cría?", None),
    "color": ("Color", None),
    "estado_salud": ("Estado de salud", None),
}


@router.get("/esquema", response_model=Esquema)
def esquema():
    art = _artefacto()
    rangos = art["rangos"]
    opciones = art["opciones"]

    numericos = []
    for nombre in art["numericas"]:
        r = rangos[nombre]
        etiqueta, unidad = ETIQUETAS.get(nombre, (nombre, None))
        numericos.append(
            CampoNumerico.model_validate(
                {
                    "nombre": nombre,
                    "etiqueta": etiqueta,
                    "minimo": r["min"],
                    "maximo": r["max"],
                    "sugerido": r["mediana"],
                    "entero": r["entero"],
                    "unidad": unidad,
                }
            )
        )

    booleanos = [
        CampoOpciones.model_validate(
            {"nombre": n, "etiqueta": ETIQUETAS.get(n, (n, None))[0], "opciones": ["No", "Sí"]}
        )
        for n in art["binarias"]
    ]

    categoricos = [
        CampoOpciones.model_validate(
            {"nombre": n, "etiqueta": ETIQUETAS.get(n, (n, None))[0], "opciones": opciones[n]}
        )
        for n in art["categoricas"]
    ]

    return Esquema.model_validate(
        {
            "objetivo": art["objetivo"],
            "clases": [c for c in ORDEN_CLASES if c in art["clases"]],
            "modelo": art["modelo"],
            "f1_macro": round(art["f1_macro_prueba"], 4),
            "entrenado_con": art["n_entrenamiento"],
            "fecha": art["fecha"],
            "numericos": numericos,
            "booleanos": booleanos,
            "categoricos": categoricos,
        }
    )


class Entrada(BaseModel):
    """Los valores llegan con el nombre de columna del modelo."""

    valores: Dict[str, Any] = Field(min_length=1)


@router.post("", response_model=Resultado)
def predecir(entrada: Entrada):
    art = _artefacto()
    pipeline = art["pipeline"]
    columnas: List[str] = art["caracteristicas"]

    faltan = [c for c in columnas if c not in entrada.valores]
    if faltan:
        raise HTTPException(status_code=422, detail=f"Faltan valores: {', '.join(faltan)}")

    fila: Dict[str, Any] = {}
    for columna in columnas:
        valor = entrada.valores[columna]
        if columna in art["numericas"] or columna in art["binarias"]:
            try:
                fila[columna] = float(valor)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=422, detail=f"'{columna}' debe ser un número (llegó: {valor!r})"
                )
        else:
            fila[columna] = str(valor)

    # Aviso cuando algún valor cae fuera del rango visto en el entrenamiento: el modelo
    # responde igual, pero extrapolar es menos fiable y quien lo lee debe saberlo.
    fuera = [
        ETIQUETAS.get(c, (c, None))[0]
        for c, r in art["rangos"].items()
        if not (r["min"] <= fila[c] <= r["max"])
    ]

    try:
        df = pd.DataFrame([fila])[columnas]
        clase = str(pipeline.predict(df)[0])
        probs = pipeline.predict_proba(df)[0]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"El modelo no pudo predecir: {exc}")

    pares = {str(c): float(p) for c, p in zip(pipeline.classes_, probs)}
    ordenadas = [
        {"clase": c, "probabilidad": round(pares[c], 4)}
        for c in ORDEN_CLASES
        if c in pares
    ]

    aviso = None
    if fuera:
        aviso = (
            "Valores fuera del rango con el que se entrenó el modelo: "
            + ", ".join(fuera)
            + ". La predicción es menos fiable."
        )

    return Resultado.model_validate(
        {
            "prediccion": clase,
            "confianza": round(max(pares.values()), 4),
            "probabilidades": ordenadas,
            "aviso": aviso,
        }
    )


# --- Interpretación con Claude ----------------------------------------------

SYSTEM_INTERPRETACION = """Eres Vaky, el asistente de CampoClaro. Acabas de recibir la \
predicción de un modelo de clasificación reproductiva sobre una vaca concreta y tienes que \
explicársela a quien maneja el establecimiento.

Lo que debes producir, en español y sin encabezados de sección:

1. Qué significa esa clasificación para esta vaca, en dos o tres frases.
2. Qué valores concretos de ESTA vaca llevan a ese resultado. Cítalos con su número y \
compáralos con lo típico del rodeo cuando lo sepas. Apóyate en el peso real que cada \
variable tiene en el modelo: si un dato llamativo pertenece a una variable que el modelo \
apenas usa, dilo en lugar de darle importancia que no tiene.
3. Entre dos y cuatro recomendaciones de manejo, concretas y accionables, en lista con \
guiones. Prioriza: lo que hay que hacer primero, primero.
4. Una frase final sobre los límites: la confianza del modelo, y que cualquier decisión \
clínica o reproductiva la valida el veterinario.

Cómo escribes:
- Directo y con el vocabulario del campo. Sin jerga de machine learning: nada de \
"features", "probabilidad a posteriori" ni "el modelo inferió".
- No inventes datos que no estén en lo que recibes. Si algo no se puede saber con estos \
valores, dilo.
- Si la confianza es baja o hay valores fuera del rango de entrenamiento, que se note en \
el tono: menos afirmación, más "conviene confirmar".
- Una confianza del 100% no es certeza: es lo que devuelve este tipo de modelo cuando el \
caso queda lejos de la frontera entre clases. Puedes decir que el caso es claro o que no \
hay ambigüedad entre categorías, pero nunca lo presentes como infalible ni digas que no \
hay ninguna duda posible.
- Nunca indiques tratamientos ni medicación. Eso es del veterinario.
- Entre 150 y 250 palabras."""


class SolicitudInterpretacion(BaseModel):
    valores: Dict[str, Any]
    prediccion: str
    confianza: float
    probabilidades: List[Dict[str, Any]] = []
    aviso: Optional[str] = None


class Interpretacion(CamelModel):
    texto: str


@router.post("/interpretacion", response_model=Interpretacion)
def interpretar(solicitud: SolicitudInterpretacion):
    # Import local: así el endpoint de predicción funciona aunque no haya clave de API.
    from .chat import MODELO, _cliente

    import anthropic

    art = _artefacto()
    client = _cliente()

    def describe(columna: str, valor: Any) -> str:
        etiqueta, unidad = ETIQUETAS.get(columna, (columna, None))
        if columna in art["binarias"]:
            texto = "sí" if float(valor) == 1 else "no"
        elif columna in art["numericas"]:
            rango = art["rangos"][columna]
            texto = f"{valor}{' ' + unidad if unidad else ''}"
            texto += f" (mediana del rodeo: {rango['mediana']}, rango {rango['min']}–{rango['max']})"
        else:
            texto = str(valor)
        return f"- {etiqueta}: {texto}"

    ficha = "\n".join(
        describe(c, solicitud.valores[c])
        for c in art["caracteristicas"]
        if c in solicitud.valores
    )

    pesos = "\n".join(
        f"- {ETIQUETAS.get(k, (k, None))[0]}: {v}"
        for k, v in list(art["importancias"].items())[:6]
    )

    reparto = ", ".join(
        f"{p['clase']} {float(p['probabilidad']) * 100:.0f}%" for p in solicitud.probabilidades
    )

    mensaje = f"""Datos de la vaca:
{ficha}

Resultado del modelo:
- Clasificación: {solicitud.prediccion}
- Confianza: {solicitud.confianza * 100:.0f}%
- Reparto entre clases: {reparto or 'no disponible'}
{f'- Advertencia: {solicitud.aviso}' if solicitud.aviso else ''}

Peso de cada variable en el modelo (cuánto empeora al quitarla; cerca de cero = casi no la usa):
{pesos}

Contexto del modelo: {art['modelo']}, entrenado con {art['n_entrenamiento']} vacas.
Sobre datos que no vio: acierta la clase exacta en el {art.get('accuracy_prueba', 0) * 100:.0f}% \
de los casos, y en el {art.get('dentro_de_una_clase', 0) * 100:.0f}% cae en la clase correcta o \
en una contigua. Su F1 macro es {round(art['f1_macro_prueba'], 3)}.

Al hablar de fiabilidad usa el porcentaje de acierto o el del margen de una clase. El F1 macro \
es un promedio del rendimiento por clase y NO significa "acierta 87 de cada 100": no lo \
traduzcas a proporciones de acierto. Las clases contiguas (Buena y Excelente, por ejemplo) se \
confunden entre sí con cierta frecuencia."""

    try:
        respuesta = client.messages.create(
            model=MODELO,
            max_tokens=1500,
            system=SYSTEM_INTERPRETACION,
            messages=[{"role": "user", "content": mensaje}],
        )
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="La ANTHROPIC_API_KEY no es válida.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Límite de la API alcanzado.")
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Error de la API de Claude ({exc.status_code}).")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="No se pudo conectar con la API de Claude.")

    if respuesta.stop_reason == "refusal":
        raise HTTPException(status_code=422, detail="El modelo declinó explicar esta predicción.")

    texto = "\n\n".join(b.text for b in respuesta.content if b.type == "text").strip()
    return Interpretacion.model_validate({"texto": texto or "No se pudo generar la explicación."})
