"""Herramientas que Claude puede ejecutar sobre el rodeo.

No se le da SQL libre al modelo: cada herramienta expone una consulta acotada
y el servidor decide cómo se agrega. Así una pregunta del chat nunca puede
convertirse en una lectura o escritura arbitraria de la base.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .risk import assess_risk, summarize

# --- Definiciones que se envían a la API -------------------------------------

AGRUPACIONES = ["nivel_riesgo", "raza", "estado", "paridad", "rango_intervalo"]
VARIABLES_NUMERICAS = [
    "intervalo_meses",
    "leche_litros",
    "condicion_corporal",
    "eventos_sanitarios",
    "paridad",
]

METRICAS = [
    "conteo",
    "promedio_intervalo",
    "promedio_leche",
    "promedio_condicion",
    "promedio_eventos",
]

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "estadisticas_generales",
        "description": (
            "Devuelve el resumen del rodeo: total de vacas, cuántas hay en riesgo alto, "
            "medio y bajo, intervalo promedio entre partos y producción promedio. "
            "Úsala para responder preguntas generales o para conocer el tamaño del rodeo "
            "antes de pedir datos más finos."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "consultar_rodeo",
        "description": (
            "Agrupa el rodeo por una dimensión y calcula una métrica en cada grupo. "
            "Es la herramienta para cualquier comparación entre categorías: riesgo por raza, "
            "producción por paridad, intervalo por estado, distribución de intervalos, etc. "
            "Devuelve una fila por grupo con la métrica y cuántas vacas lo componen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agrupar_por": {
                    "type": "string",
                    "enum": AGRUPACIONES,
                    "description": "Dimensión por la que se agrupa. 'rango_intervalo' divide en tramos de meses entre partos.",
                },
                "metrica": {"type": "string", "enum": METRICAS},
                "filtro_nivel": {
                    "type": "string",
                    "enum": ["Alto", "Medio", "Bajo"],
                    "description": "Opcional: limita el cálculo a las vacas de ese nivel de riesgo.",
                },
            },
            "required": ["agrupar_por", "metrica"],
            "additionalProperties": False,
        },
    },
    {
        "name": "listar_vacas",
        "description": (
            "Devuelve vacas individuales con sus datos y su evaluación de riesgo. "
            "Úsala cuando la pregunta sea sobre animales concretos ('cuáles son las más críticas', "
            "'qué pasa con BOV-003') y no sobre un agregado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nivel": {"type": "string", "enum": ["Alto", "Medio", "Bajo"]},
                "caravana": {
                    "type": "string",
                    "description": "Busca por coincidencia parcial de caravana, p. ej. 'BOV-00'.",
                },
                "ordenar_por": {
                    "type": "string",
                    "enum": ["intervalo", "leche", "condicion", "eventos", "score_riesgo"],
                },
                "descendente": {"type": "boolean"},
                "limite": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "datos_dispersion",
        "description": (
            "Devuelve un punto por vaca con dos variables numéricas, listo para pasar a "
            "mostrar_grafica con tipo 'dispersion'. Úsala cuando la pregunta sea si dos "
            "variables se relacionan ('¿las de peor condición corporal son las de intervalo "
            "más largo?'). Incluye el nivel de riesgo de cada vaca como grupo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "eje_x": {"type": "string", "enum": VARIABLES_NUMERICAS},
                "eje_y": {"type": "string", "enum": VARIABLES_NUMERICAS},
                "agrupar_por": {
                    "type": "string",
                    "enum": ["nivel_riesgo", "raza", "estado", "ninguno"],
                    "description": "Cómo se colorean los puntos. Por defecto nivel_riesgo.",
                },
            },
            "required": ["eje_x", "eje_y"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mostrar_grafica",
        "description": (
            "Dibuja una gráfica en el dashboard del usuario. Llámala cuando la respuesta se "
            "entienda mejor viéndola, y solo con datos que ya obtuviste de las otras herramientas.\n\n"
            "Cómo elegir el tipo:\n"
            "- 'barras': comparar una magnitud entre categorías (lo más frecuente). "
            "Si las categorías tienen nombres largos o son más de 7, usa 'barras_horizontales'.\n"
            "- 'linea': solo para una secuencia con orden natural (tramos de intervalo, paridad ascendente). "
            "Nunca para categorías sin orden como la raza.\n"
            "- 'pastel': solo para parte-de-un-todo, cuando las porciones suman el 100% de algo "
            "y basta verlas de un vistazo. Máximo 6 porciones y nunca para comparar valores "
            "parecidos (ahí van barras). Con 2 categorías usa 'dato', no medio pastel.\n"
            "- 'dispersion': para ver si dos variables numéricas se relacionan, p. ej. intervalo "
            "contra condición corporal. Pide los pares con datos_dispersion y pásalos en 'puntos'; "
            "deja 'categorias' y 'series' vacíos. Máximo 3 grupos.\n"
            "- 'dato': un solo número que es la respuesta entera. Sin gráfica de una sola barra.\n\n"
            "Usa paleta 'riesgo' cuando las categorías sean justamente Alto/Medio/Bajo, y "
            "'categorica' en cualquier otro caso. Una gráfica por idea; no repitas en gráfica "
            "algo que ya dijiste en una tabla."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["barras", "barras_horizontales", "linea", "pastel", "dispersion", "dato"],
                },
                "titulo": {"type": "string", "description": "Qué se está mirando, en pocas palabras."},
                "subtitulo": {"type": "string", "description": "Opcional: la unidad o el recorte de los datos."},
                "etiqueta_valor": {
                    "type": "string",
                    "description": "Nombre de lo que se mide, p. ej. 'vacas' o 'meses'. Va en el eje y el tooltip.",
                },
                "categorias": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Etiquetas del eje. Vacío para tipo 'dato'.",
                },
                "series": {
                    "type": "array",
                    "description": "Una entrada por serie. Para la mayoría de respuestas basta una.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nombre": {"type": "string"},
                            "valores": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["nombre", "valores"],
                        "additionalProperties": False,
                    },
                },
                "puntos": {
                    "type": "array",
                    "description": "Solo para 'dispersion'. Un punto por vaca, tal como los devuelve datos_dispersion.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "etiqueta": {"type": "string", "description": "Caravana, para el tooltip."},
                            "grupo": {"type": "string", "description": "Agrupa y colorea los puntos, p. ej. el nivel de riesgo."},
                        },
                        "required": ["x", "y"],
                        "additionalProperties": False,
                    },
                },
                "eje_x": {"type": "string", "description": "Nombre del eje horizontal en 'dispersion'."},
                "eje_y": {"type": "string", "description": "Nombre del eje vertical en 'dispersion'."},
                "paleta": {"type": "string", "enum": ["riesgo", "categorica"]},
                "decimales": {"type": "integer", "minimum": 0, "maximum": 2},
            },
            "required": ["tipo", "titulo", "categorias", "series"],
            "additionalProperties": False,
        },
    },
]


# --- Ejecución ---------------------------------------------------------------

RANGOS_INTERVALO = [
    ("< 10 meses", 0.0, 10.0),
    ("10 a 12", 10.0, 12.0),
    ("12 a 14", 12.0, 14.0),
    ("14 a 16", 14.0, 16.0),
    ("16 o más", 16.0, float("inf")),
]

_METRICA_CAMPO = {
    "promedio_intervalo": "interval_months",
    "promedio_leche": "milk_liters",
    "promedio_condicion": "body_condition",
    "promedio_eventos": "health_events",
}

_ORDEN_CAMPO = {
    "intervalo": "interval_months",
    "leche": "milk_liters",
    "condicion": "body_condition",
    "eventos": "health_events",
}


def _clave_grupo(cow: models.Cow, agrupar_por: str) -> str:
    if agrupar_por == "nivel_riesgo":
        return assess_risk(cow)["level"]
    if agrupar_por == "raza":
        return cow.breed or "Sin raza registrada"
    if agrupar_por == "estado":
        return cow.status
    if agrupar_por == "paridad":
        return f"Paridad {cow.parity}"
    for etiqueta, minimo, maximo in RANGOS_INTERVALO:
        if minimo <= cow.interval_months < maximo:
            return etiqueta
    return "Sin dato"


def _orden_grupos(agrupar_por: str, claves: List[str]) -> List[str]:
    """Las dimensiones ordinales conservan su orden natural; el resto va por tamaño."""
    if agrupar_por == "nivel_riesgo":
        preferido = ["Alto", "Medio", "Bajo"]
    elif agrupar_por == "rango_intervalo":
        preferido = [etiqueta for etiqueta, _, _ in RANGOS_INTERVALO]
    elif agrupar_por == "paridad":
        return sorted(claves, key=lambda c: int(c.split()[-1]))
    else:
        return claves
    return [c for c in preferido if c in claves] + [c for c in claves if c not in preferido]


def estadisticas_generales(db: Session) -> Dict[str, Any]:
    cows = db.scalars(select(models.Cow)).all()
    resumen = summarize(cows)
    return {
        "total_vacas": resumen["total"],
        "riesgo_alto": resumen["high"],
        "riesgo_medio": resumen["medium"],
        "riesgo_bajo": resumen["low"],
        "intervalo_promedio_meses": round(resumen["average_interval"], 2),
        "produccion_promedio_litros": round(resumen["average_milk"], 2),
        "umbral_alerta_meses": 14,
    }


def consultar_rodeo(
    db: Session,
    agrupar_por: str,
    metrica: str,
    filtro_nivel: Optional[str] = None,
) -> Dict[str, Any]:
    cows = db.scalars(select(models.Cow)).all()
    if filtro_nivel:
        cows = [c for c in cows if assess_risk(c)["level"] == filtro_nivel]

    grupos: Dict[str, List[models.Cow]] = {}
    for cow in cows:
        grupos.setdefault(_clave_grupo(cow, agrupar_por), []).append(cow)

    filas = []
    for clave in _orden_grupos(agrupar_por, list(grupos)):
        miembros = grupos[clave]
        if metrica == "conteo":
            valor: float = len(miembros)
        else:
            campo = _METRICA_CAMPO[metrica]
            valor = round(sum(getattr(c, campo) for c in miembros) / len(miembros), 2)
        filas.append({"categoria": clave, "valor": valor, "vacas_en_grupo": len(miembros)})

    return {
        "agrupado_por": agrupar_por,
        "metrica": metrica,
        "filtro_nivel": filtro_nivel,
        "vacas_consideradas": len(cows),
        "filas": filas,
    }


def listar_vacas(
    db: Session,
    nivel: Optional[str] = None,
    caravana: Optional[str] = None,
    ordenar_por: Optional[str] = None,
    descendente: bool = True,
    limite: int = 10,
) -> Dict[str, Any]:
    stmt = select(models.Cow)
    if caravana:
        stmt = stmt.where(models.Cow.ear_tag.ilike(f"%{caravana}%"))
    cows = list(db.scalars(stmt))

    if nivel:
        cows = [c for c in cows if assess_risk(c)["level"] == nivel]

    if ordenar_por == "score_riesgo":
        cows.sort(key=lambda c: assess_risk(c)["score"], reverse=descendente)
    elif ordenar_por:
        cows.sort(key=lambda c: getattr(c, _ORDEN_CAMPO[ordenar_por]), reverse=descendente)
    else:
        cows.sort(key=lambda c: c.ear_tag)

    recortadas = cows[: max(1, min(limite, 50))]
    return {
        "coincidencias_totales": len(cows),
        "mostradas": len(recortadas),
        "vacas": [
            {
                "caravana": c.ear_tag,
                "raza": c.breed,
                "estado": c.status,
                "paridad": c.parity,
                "intervalo_meses": c.interval_months,
                "leche_litros_dia": c.milk_liters,
                "condicion_corporal": c.body_condition,
                "eventos_sanitarios": c.health_events,
                "ultimo_parto": c.last_calving,
                "ultimo_servicio": c.last_service,
                "riesgo": assess_risk(c)["level"],
                "score_riesgo": assess_risk(c)["score"],
                "notas": c.notes,
            }
            for c in recortadas
        ],
    }


_VARIABLE_CAMPO = {
    "intervalo_meses": "interval_months",
    "leche_litros": "milk_liters",
    "condicion_corporal": "body_condition",
    "eventos_sanitarios": "health_events",
    "paridad": "parity",
}


def datos_dispersion(
    db: Session,
    eje_x: str,
    eje_y: str,
    agrupar_por: str = "nivel_riesgo",
) -> Dict[str, Any]:
    cows = db.scalars(select(models.Cow).order_by(models.Cow.ear_tag)).all()
    campo_x, campo_y = _VARIABLE_CAMPO[eje_x], _VARIABLE_CAMPO[eje_y]

    puntos = []
    for cow in cows:
        punto: Dict[str, Any] = {
            "x": getattr(cow, campo_x),
            "y": getattr(cow, campo_y),
            "etiqueta": cow.ear_tag,
        }
        if agrupar_por != "ninguno":
            punto["grupo"] = _clave_grupo(cow, agrupar_por)
        puntos.append(punto)

    return {
        "eje_x": eje_x,
        "eje_y": eje_y,
        "agrupado_por": agrupar_por,
        "n": len(puntos),
        "puntos": puntos,
    }


def ejecutar(db: Session, nombre: str, entrada: Dict[str, Any]) -> Dict[str, Any]:
    """Despacha una llamada de herramienta. `mostrar_grafica` se maneja aparte."""
    if nombre == "estadisticas_generales":
        return estadisticas_generales(db)
    if nombre == "consultar_rodeo":
        return consultar_rodeo(db, **entrada)
    if nombre == "listar_vacas":
        return listar_vacas(db, **entrada)
    if nombre == "datos_dispersion":
        return datos_dispersion(db, **entrada)
    raise ValueError(f"Herramienta desconocida: {nombre}")
