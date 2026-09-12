# CampoClaro

Frontend Next.js + backend FastAPI + SQLite, orquestados con Docker Compose.

## Levantar

```bash
docker compose up
```

- Frontend: http://localhost:3000
- API: http://localhost:8001
- Docs interactivas (Swagger): http://localhost:8001/docs

Los puertos se cambian en `.env` (`FRONTEND_PORT`, `BACKEND_PORT`).

## Estructura

```
backend/          FastAPI + SQLAlchemy
  app/main.py     Endpoints
  app/models.py   Tabla cows
  app/risk.py     Motor de riesgo (espejo de lib/risk-engine.ts)
  app/seed.py     Rodeo demo inicial
  app/chat.py     Vaky: bucle de herramientas contra la API de Claude
  app/chat_tools.py  Las herramientas que Vaky puede ejecutar
frontend/         Next.js (lib/api.ts es el cliente HTTP)
docker-compose.yml
```

## Volúmenes

- `./backend:/app` y `./frontend:/app` están montados como bind mounts: al editar código
  en tu máquina, uvicorn y Next recargan solos, sin reconstruir la imagen.
- La base SQLite es `backend/data/campoclaro.db`, un bind mount más: está en tu
  carpeta, se abre con cualquier visor de SQLite y sobrevive a `docker compose down`.
  Para empezar de cero, borra el archivo y reinicia el backend — se vuelve a crear
  con el rodeo demo. Está en `.gitignore`, así que no llega al repositorio.
- `node_modules` y `.next` son volúmenes anónimos para que el bind mount del frontend
  no pise las dependencias instaladas dentro de la imagen.

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/health` | Healthcheck |
| GET | `/api/cows` | Lista vacas (filtros `?search=` y `?level=Alto\|Medio\|Bajo`) |
| GET | `/api/cows/{id}` | Ficha individual |
| POST | `/api/cows` | Crear vaca |
| PATCH | `/api/cows/{id}` | Actualizar campos |
| DELETE | `/api/cows/{id}` | Eliminar |
| GET | `/api/cows/{id}/risk` | Evaluación de riesgo |
| GET | `/api/summary` | KPIs del rodeo |
| GET | `/api/export.csv` | Exportar CSV |
| POST | `/api/import` | Importar CSV (multipart `file`), actualiza por caravana |
| POST | `/api/chat` | Vaky: recibe `{messages}`, devuelve `{reply, charts, toolsUsed}` |

El JSON usa camelCase (`earTag`, `intervalMonths`) para coincidir con `lib/types.ts`.
Cada vaca devuelta incluye su bloque `risk` calculado en el servidor.

## Modelo de clasificación

`modelo/modelo_clasificacion.ipynb` entrena un clasificador sobre `olinda_clean.csv`
(2500 vacas) que predice la clasificación reproductiva — Excelente / Buena / Regular /
Mala — y lo exporta a `modelo_clasificacion_reproductiva.joblib`.

```bash
cd modelo && python3 -m notebook modelo_clasificacion.ipynb
```

Gradient Boosting, **F1 macro 0.871** en datos que no vio (el baseline de clase
mayoritaria da 0.167), con el 99,2% de las predicciones dentro de una clase de margen.
El artefacto guarda el pipeline completo, preprocesado incluido, así que recibe un
DataFrame con las columnas originales y no hay que replicar nada a mano.

Dos decisiones que condicionan las métricas: se mide con **F1 macro** y no accuracy
porque *Excelente* es el 3,8% del rodeo, y se excluye `candidata_descarte` de las
variables predictoras porque es **consecuencia** de clasificar a la vaca, no un dato
previo — usarla subiría las métricas y el modelo fallaría en el campo.

### El modelo dentro de la plataforma

La vista **Modelo** del dashboard tiene el formulario: ingresas los datos de una vaca y
devuelve la clasificación con las probabilidades de cada clase, y debajo la lectura de
Vaky —qué significa, qué valores de *esa* vaca la explican y recomendaciones de manejo.

El backend monta `./modelo` en solo lectura y carga el artefacto una vez en memoria. Al
reentrenar desde el notebook basta reiniciar el backend:

```bash
docker compose restart backend
```

| Método | Ruta | Para qué |
| --- | --- | --- |
| GET | `/api/prediccion/esquema` | Campos, rangos y opciones — el formulario se construye con esto |
| POST | `/api/prediccion` | Clasifica: `{valores}` → clase + probabilidades |
| POST | `/api/prediccion/interpretacion` | La explicación de Vaky sobre esa predicción |

Tres decisiones de esta integración:

- **El artefacto es autodescriptivo.** Lleva dentro las opciones válidas, los rangos de
  entrenamiento y las importancias de cada variable, así que el backend no necesita leer
  el CSV ni repetir las listas a mano, y el formulario se genera solo.
- **Predicción y explicación son endpoints separados.** La clase aparece al instante y el
  texto llega después; sin `ANTHROPIC_API_KEY` el clasificador sigue funcionando igual.
- **Si un valor sale del rango de entrenamiento, la respuesta avisa.** El modelo contesta
  de todos modos, pero extrapolar es menos fiable y quien lo lee debe saberlo.

`scikit-learn` va fijado a la versión que serializó el modelo (1.6.1): cargar el pipeline
con otra puede dar avisos de incompatibilidad o fallar.

## Vaky, el asistente

El botón con la carita de vaca abajo a la derecha abre a **Vaky**: consulta la base
con Claude y dibuja gráficas en el dashboard.

Para activarlo, pega tu clave en `ANTHROPIC_API_KEY` dentro de `.env`
(la consigues en https://console.anthropic.com/settings/keys) y reinicia el backend:

```bash
docker compose up -d backend
```

Sin clave el resto de la app funciona igual; solo Vaky responde 503 con el aviso.
El modelo se cambia con `ANTHROPIC_MODEL` (por defecto `claude-opus-5`).

**Vaky no escribe SQL.** Tiene cinco herramientas acotadas — resumen del rodeo,
agregación por dimensión, listado de vacas, pares de variables para dispersión y
dibujar una gráfica — así que una pregunta del chat no puede convertirse en una
lectura o escritura arbitraria de la base. Tampoco puede modificar datos: todas
son de lectura.

Sabe dibujar barras (verticales y horizontales), línea, **pastel**, **dispersión**
y el dato suelto. Elige la forma según lo que la pregunta necesite, pero si le pides
una forma concreta te la da: es tu dashboard.

Las gráficas se apilan en la vista de Inicio bajo "Generado por Vaky" y se quitan
con el botón Limpiar. Sus paletas están validadas para daltonismo contra la
superficie real de las tarjetas; el ámbar no alcanza 3:1 de contraste, por eso las
barras llevan siempre su valor escrito.

Dos detalles de la dispersión que no son estéticos:

- **Los puntos se distinguen por forma además de color** (círculo, triángulo, rombo).
  En una nube los grupos se mezclan, y ahí la paleta de riesgo falla: con
  deuteranopía el verde y el rojo quedan a ΔE 4.2, indistinguibles. La forma es
  el canal que sostiene la identidad cuando el color no puede.
- **Sus ejes no arrancan en cero**, al contrario que las barras. En una barra el cero
  es obligatorio porque la longitud representa la magnitud; en una dispersión
  forzarlo apiña la nube en una esquina y esconde la relación que se busca.

El pastel se limita a 6 porciones y pliega la cola en "Otras": más allá de eso los
sectores no se distinguen, y generar más tonos para ellos empeora el problema.

## Créditos

La foto del hero (`frontend/public/hero-campo.jpg`) es de Unsplash, bajo su licencia
gratuita para uso comercial. Reemplázala por una foto propia del establecimiento
manteniendo el mismo nombre de archivo.

El icono de Vaky (`frontend/public/cow-face.png`) viene de icon-icons.com; revisa
la licencia de ese icono en su página si vas a publicar la app.

## Sin Docker

```bash
cd backend && pip install -r requirements.txt && DATA_DIR=./data uvicorn app.main:app --reload
cd frontend && pnpm install && pnpm dev
```
