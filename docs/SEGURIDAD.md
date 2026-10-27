# Seguridad y escaneo

## Gestion de secretos

- Todo secreto vive en `.env`, que esta en `.gitignore`.
- `.env.example` solo contiene placeholders.
- No hay contrasenas, tokens ni claves en el codigo, los DAGs, la API o el frontend.
- Las credenciales de Airflow, PostgreSQL, JWT y Fernet se inyectan por variables de entorno.
- Los usuarios admin y viewer se siembran desde `ADMIN_*` y `VIEWER_*` con `crypt()` de pgcrypto.
- PostgreSQL no publica puertos al host; solo es accesible dentro de la red de Compose.

## Roles de base de datos

| Rol | Acceso |
| --- | --- |
| `airflow` | Solo base de metadata de Airflow |
| `ingest_writer` | DML en `raw` |
| `transform_writer` | Lectura de raw y DML en staging, curated, quality, pipeline y ai |
| `api_reader` | SELECT en curated, metricas, pipeline, reportes, anomalias, usuarios y INSERT en query_log |

La API usa un unico engine de lectura con el rol `api_reader`. Ningun endpoint puede leer raw ni
staging.

## Plataforma

- JWT HS256 con expiracion de 480 minutos.
- Password hashing bcrypt compatible con pgcrypto.
- Validacion de rol en el backend con dependencias de FastAPI.
- CORS limitado al origen del frontend.
- Consultas parametrizadas en todos los endpoints.
- Filtros de orden por lista blanca.
- Respuestas de error sin trazas internas.
- Documentacion OpenAPI en `/docs`.
- Uvicorn usa `--no-access-log` para no registrar el token SSE del query string.
- El viewer recibe solo el resumen de calidad; el detalle de reglas y el conteo de motivos se
  reservan al admin y se eliminan de su respuesta.

## Datos externos y LLM

- USGS se consume por HTTPS, con timeout y validacion de estado, content type y estructura GeoJSON.
- `place` se sanea antes de guardarse y antes de llegar al modelo.
- El prompt del agente declara que la pregunta es no confiable y que debe ignorar instrucciones
  embebidas.
- El SQL generado se parsea con sqlglot, se restringe a `curated.events`, se ejecuta en una
  transaccion de solo lectura, con `statement_timeout` y con el rol `api_reader`.
- El reporte narrativo y la respuesta del agente validan numeros, lugares, valores obligatorios y
  contradicciones; si fallan, caen a una plantilla determinista.
- Las ejecuciones de IA se auditan en `ai.runs` y las consultas NL en `ai.query_log`.

## Evidencia de control de acceso

```text
GET  /api/kpis                    sin token  -> 401
GET  /api/kpis                    viewer     -> 200
GET  /api/admin/ai-runs           viewer     -> 403
POST /api/admin/backfill          viewer     -> 403
```

## Escaneo ejecutado

Herramienta: bandit 1.8.0 sobre `api/app`.

```bash
docker compose exec -T api bandit -r app -f txt
```

Resultado:

```text
Total lines of code: 1837
High: 0
Medium: 13
Low: 2
```

Hallazgos y triage:

- B608 (13, confianza baja): construccion de SQL con f-strings en filtros y orden. Los fragmentos interpolados son columnas de una lista blanca (`SORT_COLUMNS`), clausulas fijas o
  ventanas de tiempo convertidas a entero y acotadas entre 1 y 1440 horas. Los valores del usuario
  viajan como parametros de SQLAlchemy. Riesgo aceptado y documentado.
- B110 (1, confianza alta): `try/except/pass` al registrar la auditoria de una consulta NL. Es
  intencional: un fallo del log de auditoria no debe tumbar la respuesta al usuario.
- B406 (1, confianza alta): uso de `xml.sax.saxutils.escape` en la exportacion PDF. Se usa para
  escapar texto antes de ReportLab, no para parsear XML. Falso positivo.

Los registros que no pasan validacion no se cargan en staging ni en curated; su payload original
queda en raw y `quality.metrics` conserva el conteo y motivo. No se mantiene una tabla aparte de
descartes.

No se encontraron hallazgos de severidad alta. No hay secretos en el repositorio; `.env` esta
ignorado. Para una entrega real se agregaria `gitleaks` y `pip-audit` en CI.

## Limitaciones conscientes

- El token SSE viaja en el query string porque `EventSource` no permite cabeceras. En produccion se
  usaria cookie HttpOnly o ticket efimero.
- El rate limiting del login no esta implementado; se delegaria a un gateway o a slowapi.
- La base de datos no tiene TLS interno en el entorno local de Docker.
