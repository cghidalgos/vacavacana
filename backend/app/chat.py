"""Endpoint del asistente: Claude con herramientas sobre el rodeo."""

import json
import os
from typing import Any, Dict, List, Literal, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import chat_tools
from .database import get_db
from .schemas import CamelModel

router = APIRouter(prefix="/api/chat", tags=["asistente"])

MODELO = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
# Tope de vueltas del bucle: evita que una conversación se quede iterando
# herramientas indefinidamente si el modelo no converge.
MAX_VUELTAS = 8

SYSTEM = """Eres Vaky, el asistente de CampoClaro, un sistema de apoyo a la decisión para \
el manejo reproductivo de un rodeo bovino. Hablas con la persona que maneja el establecimiento.\n\nSi te preguntan quién eres, preséntate como Vaky en una frase y sigue con lo que puedes hacer; \nno repitas tu nombre en cada respuesta.

Sobre el dominio:
- La señal central es el intervalo entre partos. La línea base marca riesgo Alto a partir \
de 14 meses, Medio entre 12 y 14, y Bajo por debajo de 12.
- Ese umbral es una referencia operativa para decidir a qué vaca mirar primero, no un \
diagnóstico. La clasificación sale de una regla explícita, no de un modelo entrenado.
- Nunca des indicaciones de tratamiento ni sustituyas el criterio del veterinario. Si te \
preguntan qué hacer clínicamente con un animal, di qué muestran los datos y recomienda \
consultarlo con el veterinario.

Cómo trabajas:
- Responde siempre en español, con el tono directo de alguien que conoce el campo.
- Consulta los datos con las herramientas antes de afirmar cualquier número. Nunca \
inventes ni estimes cifras que no obtuviste de una herramienta.
- Dibuja una gráfica con mostrar_grafica cuando la respuesta se entienda mejor viéndola \
(comparaciones y distribuciones), y no la uses para un dato suelto ni para repetir algo \
que ya explicaste.
- Cuando eliges tú la forma, hazlo por el trabajo que tiene que hacer quien lee: barras \
para comparar magnitudes, pastel cuando las porciones son partes de un mismo todo y basta \
verlas de un vistazo, dispersión para relacionar dos variables numéricas, línea para una \
secuencia ordenada. Entre barras y pastel para lo mismo, elige barras: dos porciones \
parecidas no se distinguen en un pastel.
- Si te piden una forma concreta, dásela. Es su dashboard y sabe lo que quiere ver. Si \
otra forma se leería mejor, dibuja la que pidió y dilo en una frase; si quiere, puedes \
añadir la otra además, nunca en lugar de la suya.
- Sé breve: dos o tres frases más la gráfica suelen alcanzar. Da el número y lo que \
implica, no el procedimiento que seguiste.
- Si los datos no alcanzan para responder, dilo claramente en lugar de aproximar. Cuando un promedio se apoya en pocos animales, dilo: es más útil que el número solo.
- No menciones tus herramientas ni su nombre: quien te lee ve una app, no el sistema por dentro. En lugar de "usa listar_vacas", di "conviene mirar vaca por vaca"."""


class MensajeEntrada(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[MensajeEntrada] = Field(min_length=1)


class Serie(CamelModel):
    nombre: str
    valores: List[float]


class Punto(CamelModel):
    x: float
    y: float
    etiqueta: Optional[str] = None
    grupo: Optional[str] = None


class Grafica(CamelModel):
    tipo: str
    titulo: str
    subtitulo: Optional[str] = None
    etiqueta_valor: Optional[str] = None
    categorias: List[str] = []
    series: List[Serie] = []
    puntos: List[Punto] = []
    eje_x: Optional[str] = None
    eje_y: Optional[str] = None
    paleta: str = "categorica"
    decimales: int = 0


class ChatResponse(CamelModel):
    reply: str
    charts: List[Grafica]
    tools_used: List[str]


def _cliente() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Falta ANTHROPIC_API_KEY. Escribe tu clave en el archivo .env de la raíz "
                "del proyecto y reinicia con: docker compose up -d backend"
            ),
        )
    return anthropic.Anthropic()


@router.post("", response_model=ChatResponse)
def conversar(payload: ChatRequest, db: Session = Depends(get_db)):
    client = _cliente()

    messages: List[Dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in payload.messages
    ]
    graficas: List[Dict[str, Any]] = []
    usadas: List[str] = []
    # El modelo puede escribir texto en la misma respuesta en que pide una
    # herramienta. Ese texto es parte de la respuesta, así que se acumula: quedarse
    # solo con la última vuelta deja frases sueltas sin su contexto.
    partes: List[str] = []

    for _ in range(MAX_VUELTAS):
        try:
            response = client.messages.create(
                model=MODELO,
                max_tokens=4096,
                system=SYSTEM,
                tools=chat_tools.TOOLS,
                messages=messages,
            )
        except anthropic.AuthenticationError:
            raise HTTPException(status_code=401, detail="La ANTHROPIC_API_KEY no es válida.")
        except anthropic.RateLimitError:
            raise HTTPException(
                status_code=429, detail="Límite de la API alcanzado. Intenta en unos segundos."
            )
        except anthropic.APIStatusError as exc:
            raise HTTPException(
                status_code=502, detail=f"Error de la API de Claude ({exc.status_code})."
            )
        except anthropic.APIConnectionError:
            raise HTTPException(
                status_code=502, detail="No se pudo conectar con la API de Claude."
            )

        if response.stop_reason == "refusal":
            raise HTTPException(
                status_code=422, detail="El modelo declinó responder a esa consulta."
            )

        texto = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
        if texto:
            partes.append(texto)

        if response.stop_reason != "tool_use":
            return ChatResponse.model_validate(
                {
                    "reply": "\n\n".join(partes) or "No pude generar una respuesta para eso.",
                    "charts": graficas,
                    "tools_used": usadas,
                }
            )

        messages.append({"role": "assistant", "content": response.content})

        # Todos los tool_result de una misma respuesta van juntos en un solo mensaje.
        resultados: List[Dict[str, Any]] = []
        for bloque in response.content:
            if bloque.type != "tool_use":
                continue
            usadas.append(bloque.name)
            try:
                if bloque.name == "mostrar_grafica":
                    grafica = Grafica.model_validate(bloque.input)
                    graficas.append(grafica.model_dump(by_alias=True))
                    salida: Any = {
                        "ok": True,
                        "mensaje": f"Gráfica '{grafica.titulo}' añadida al dashboard.",
                    }
                else:
                    salida = chat_tools.ejecutar(db, bloque.name, dict(bloque.input))
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": bloque.id,
                        "content": json.dumps(salida, ensure_ascii=False, default=str),
                    }
                )
            except Exception as exc:  # el modelo debe poder corregir y reintentar
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": bloque.id,
                        "content": f"Error al ejecutar {bloque.name}: {exc}",
                        "is_error": True,
                    }
                )

        messages.append({"role": "user", "content": resultados})

    raise HTTPException(
        status_code=504,
        detail="La consulta necesitó demasiados pasos. Prueba con una pregunta más concreta.",
    )
