# Evidencia de ejecucion

Fecha de la evidencia: 2026-10-27. Los conteos son una foto de ese momento y siguen
creciendo con la ingesta automatica cada cinco minutos.
Entorno: Ubuntu 24.04, Docker Desktop 28.3.3, Docker Compose v2.39.2, 12 CPUs y 3.6 GB asignados
a Docker. Python 3.12 en host y contenedores. Ollama local con `qwen2.5:3b` escuchando en
`127.0.0.1:11434` y accesible desde la API por `host.docker.internal`.

## 1. Servicios

```text
NAME                                      STATUS
airflow-scheduler-1                       Up (healthy)
airflow-webserver-1                       Up (healthy)
api-1                                     Up
postgres-1                                Up (healthy)
web-1                                     Up
```

Airflow: metadatabase healthy, scheduler healthy, 4 DAGs sin errores de importacion.

## 2. Conteos reales en PostgreSQL

```text
raw_responses | raw_events | staging | curated | curated_ids | metrics | anomalies | reports | nl_queries
-------------+------------+---------+---------+-------------+---------+-----------+---------+-----------
          39 |       1994 |    1984 |    1984 |        1984 |      38 |         2 |       1 |        37
```

- 1 984 eventos publicados en curated.
- 1 984 ids distintos: cero duplicados.
- 10 registros no superaron la validacion y no se cargaron en staging ni curated. Su payload
  original sigue en raw y `quality.metrics` conserva el conteo y el motivo; no existe una tabla
  separada de descartes.
- Puntaje de calidad 99.5: 1 984 aprobados de 1 994 evaluados.

## 3. KPIs de la API

```json
{
  "events_24h": 36,
  "events_previous_24h": 38,
  "max_magnitude": 4.9,
  "avg_magnitude": 2.4,
  "tsunami_events": 0,
  "significant_events": 10,
  "total_events": 1984,
  "quality_score": 99.5,
  "anomalies_24h": 2,
  "last_update": "2026-10-27T14:45:03.917534+00:00",
  "freshness_seconds": 191
}
```

La frescura se calcula contra la ultima compuerta de calidad aprobada, no contra el ultimo cambio
de una fila. Asi refleja la ultima carga exitosa del pipeline.

## 4. DAGs ejecutados

```text
ingest_usgs       scheduled__2026-10-27T14:40:00+00:00        success
transform_quality dataset_triggered__2026-10-27T14:45:01+00:00 success
backfill_usgs     manual__2026-10-27T12:30:06+00:00            success
daily_ai          manual__2026-10-27T14:46:53+00:00            success
```

La ingesta corre cada cinco minutos. El Dataset `sismowatch://raw/events` dispara la transformacion
sin intervencion manual. El backfill se lanzo desde la API con rol admin.

## 5. Pruebas automatizadas

```text
Airflow: 14 passed
API:     30 passed
```

Cobertura funcional:

- Transformacion GeoJSON valida e invalida.
- Reglas de calidad y compuerta.
- Importacion de todos los DAGs y schedule por Dataset.
- Validador de numeros y contradicciones del reporte IA.
- Intents de saludo, agradecimiento, despedida, identidad, capacidades, groserias y desconocidos.
- Respuesta natural de conteos, eventos y regiones; validacion de numeros, lugares y valores.
- Endpoints sin token: 401.
- Viewer en accion admin: 403.
- Validador SQL: SELECT permitido, DML rechazado, otros schemas rechazados, CTE permitido, limite
  seguro.

Reproduccion:

```bash
bash scripts/tests.sh
```

## 6. Idempotencia

Se ejecuto `transform_quality` dos veces sobre el mismo raw y luego un backfill completo de 30 dias.

```text
Antes:   curated = 1971
Despues: curated = 1971, ids = 1971, duplicados = 0
```

La clave primaria `id` y el `ON CONFLICT DO UPDATE` garantizan que repetir el intervalo no duplica.
El backfill reutiliza el mismo upsert y tampoco crea filas repetidas.

## 7. Reporte con IA

```text
status:         ollama
numbers_valid:  true
model:          qwen2.5:3b
prompt:         report_v3
generated_at:   2026-10-27 14:46:55 UTC
```

```text
El dia de hoy se registraron 36 eventos sismicos en comparacion con los 38 del dia anterior. La
magnitud media fue de 2.4, sin tsunamis y hubo un evento de maxima magnitud de 4.9 en la region de
La Tirana, Chile.
```

El reporte paso la validacion de numeros y afirmaciones. Si el modelo falla o miente, el sistema
publica la plantilla determinista y marca el estado como `fallback_validacion`. Cada llamada queda
en `ai.runs` con modelo, tokens, latencia y costo cero por ser local.

Anomalias detectadas:

```text
2026-10-27 11:00 UTC  11 eventos  z=4.79  severidad media
2026-10-24 08:00 UTC   8 eventos  z=3.17  severidad baja
```

## 8. Agente conversacional

Saludo: `Hola`

```json
{
  "answer": "Hola, soy SismoWatch, tu asistente de monitoreo sísmico. Puedo decirte cuántos sismos hubo, cuál fue el de mayor magnitud, qué regiones están más activas o mostrarte los eventos recientes.",
  "intent": "saludo",
  "answer_provider": "reglas",
  "row_count": 0,
  "sql": null
}
```

Tiempo de respuesta del saludo: 7 ms. No invoca Ollama, no ejecuta SQL y no muestra tabla.

Conteo: `Cuantos sismos se registraron en las ultimas 24 horas?`

```json
{
  "answer": "Se registraron 36 eventos sísmicos en las últimas 24 horas.",
  "answer_provider": "ollama",
  "provider": "reglas",
  "row_count": 1
}
```

Tiempo: 2.9 s. La respuesta natural aparece arriba y la tabla de una fila queda debajo como
evidencia.

Maximo: `Cual fue el sismo de mayor magnitud en los ultimos 7 dias?`

```json
{
  "answer": "El sismo de mayor magnitud en los últimos 7 días tuvo una magnitud de 7.0 ocurrido el 22 de octubre de 2026 a las 14:33 UTC, cerca de Nagqu, China.",
  "answer_provider": "ollama",
  "provider": "reglas",
  "row_count": 1
}
```

La tabla debajo muestra `id=us6000u43g`, magnitud 7.0 y lugar. Si el modelo inventa un lugar que no
esta en `place`/`region`, la validacion descarta la respuesta y usa el fallback determinista.

Limite solicitado: `ultimos 3 terremotos`

```json
{
  "answer": "Los eventos más relevantes fueron: El evento en 78 km WNW of Ninilchik, Alaska ...",
  "row_count": 3,
  "sql": "SELECT ... ORDER BY event_time DESC LIMIT 3"
}
```

El agente respeta el numero pedido y la tabla muestra exactamente tres filas. Tiempo: 9 ms.

Seguimiento: `donde?` despues de un conteo de las ultimas 2 horas

```json
{
  "answer": "Los eventos más relevantes fueron: El evento en 52 km WNW of Beluga, Alaska con magnitud 1.7 ...",
  "answer_provider": "reglas",
  "provider": "reglas",
  "row_count": 10
}
```

Tiempo: 15 ms. El historial de seis mensajes se usa para resolver la ventana temporal. Para listas de
lugares se usa formateo determinista para no inventar ubicaciones.

Mensajes fuera de alcance y groserias tambien se resuelven sin SQL ni tabla. Cada consulta de datos
se audita en `ai.query_log`.

## 9. Tiempo real

Se verifico SSE con el token de viewer:

```text
retry: 5000

data: {"id": "us6000tzss", "mag": 4.5, "place": "35 km SW of Tambolaka, Indonesia",
       "event_time": "2026-10-05T21:38:05", "updated_at": "2026-10-27T12:20:09"}
```

El dashboard muestra el indicador EN VIVO, la hora de actualizacion y la lista de eventos recientes.
El navegador reconecta automaticamente ante cortes.

## 10. Control de acceso

```text
GET  /api/kpis                 sin token  -> 401
GET  /api/kpis                 viewer     -> 200
GET  /api/admin/ai-runs        viewer     -> 403
POST /api/admin/backfill       viewer     -> 403
```

## 11. Exportaciones

```text
reportes CSV: 200, 376 bytes
reportes PDF: 200, 1 933 bytes, PDF 1.4 de 1 pagina
```

## 12. Escaneo de seguridad

```text
bandit 1.8.0 sobre api/app
High: 0
Medium: 13 (B608, confianza baja, SQL con columnas de lista blanca, clausulas fijas o intervalos
             y limites enteros acotados)
Low: 2 (B110 en auditoria y B406 por escape HTML para PDF)
```

Salida completa: [bandit.txt](bandit.txt). Triage en [SEGURIDAD.md](SEGURIDAD.md).

## 13. Capturas

- [Login](capturas/01-login.png)
- [Dashboard en vivo (actualizado)](capturas/12-dashboard-en-vivo.png)
- [Dashboard vista completa y mapa](capturas/02-dashboard.png)
- [Agente IA - Saludo sin SQL ni tabla](capturas/13-agente-ia-saludo.png)
- [Agente IA - Consulta 24h con SQL validado](capturas/14-agente-ia-consulta-24h.png)
- [Agente IA - Sismo de mayor magnitud](capturas/10-agente-maximo.png)
- [Agente IA - Ultimos 3 terremotos](capturas/11-agente-tres-terremotos.png)
- [Reportes diarios generados con IA (detalle validado)](capturas/15-reporte-ia-validado.png)
- [Estado del pipeline, calidad y anomalias](capturas/16-pipeline-calidad-anomalias.png)
- [Administracion y auditoria de IA](capturas/17-admin-auditoria-ia.png)
- [Airflow con los cuatro DAGs ejecutados](capturas/08-airflow.png)

## 14. Reproduccion completa

```bash
docker compose up -d --build
bash scripts/verify.sh
bash scripts/tests.sh
```

`verify.sh` valida salud, login, KPIs, eventos, pipeline, 401/403, integridad de curated,
duplicados, reporte IA, saludo sin SQL y respuesta natural sin filas crudas. No inventa datos: usa
la base y la API reales.
