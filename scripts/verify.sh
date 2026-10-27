#!/usr/bin/env bash
set -euo pipefail

source .env

BASE_API="http://localhost:8000"
BASE_WEB="http://localhost:3000"

echo "== Servicios =="
docker compose ps

echo "== Salud =="
curl -fsS "$BASE_API/api/health" | jq
curl -fsS -o /dev/null -w "web=%{http_code}\n" "$BASE_WEB/"

echo "== Login admin =="
ADMIN_TOKEN=$(curl -fsS -X POST "$BASE_API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" | jq -r .access_token)
test -n "$ADMIN_TOKEN"
echo "admin_token_ok"

echo "== Login viewer =="
VIEWER_TOKEN=$(curl -fsS -X POST "$BASE_API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$VIEWER_EMAIL\",\"password\":\"$VIEWER_PASSWORD\"}" | jq -r .access_token)
test -n "$VIEWER_TOKEN"
echo "viewer_token_ok"

echo "== KPIs =="
curl -fsS "$BASE_API/api/kpis" -H "Authorization: Bearer $ADMIN_TOKEN" | jq \
  '{events_24h,max_magnitude,avg_magnitude,quality_score,freshness_seconds}'

echo "== Eventos =="
curl -fsS "$BASE_API/api/events?limit=1" -H "Authorization: Bearer $ADMIN_TOKEN" | jq \
  '{total,first:.items[0].id}'

echo "== Pipeline =="
curl -fsS "$BASE_API/api/pipeline/status" -H "Authorization: Bearer $ADMIN_TOKEN" | jq \
  '{runs:[.runs[]|{dag_id,status}],quality:.quality.score,freshness_seconds}'

echo "== Control de acceso =="
test "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_API/api/kpis")" = "401"
test "$(curl -s -o /dev/null -w '%{http_code}' "$BASE_API/api/admin/ai-runs" -H "Authorization: Bearer $VIEWER_TOKEN")" = "403"
test "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_API/api/admin/backfill" -H "Authorization: Bearer $VIEWER_TOKEN" -H 'Content-Type: application/json' -d '{"days":1}')" = "403"
echo "auth_ok"

echo "== Integridad de curated =="
docker compose exec -T postgres psql -U postgres -d sismowatch -tAc \
  "SELECT 'curated=' || count(*) || ' ids=' || count(DISTINCT id) FROM curated.events;"

echo "== Duplicados =="
DUPLICATES=$(docker compose exec -T postgres psql -U postgres -d sismowatch -tAc \
  "SELECT count(*) FROM (SELECT id FROM curated.events GROUP BY id HAVING count(*) > 1) d;")
test "$DUPLICATES" = "0"
echo "duplicates=0"

echo "== Reporte IA =="
curl -fsS "$BASE_API/api/reports?page_size=1" -H "Authorization: Bearer $ADMIN_TOKEN" | jq \
  '{total,status:.items[0].status,numbers_valid:.items[0].numbers_valid}'

echo "== Agente: saludo sin IA ni SQL =="
GREETING=$(curl -fsS -X POST "$BASE_API/api/ask" -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hola"}')
echo "$GREETING" | jq '{answer,intent,provider,answer_provider,row_count}'
test "$(echo "$GREETING" | jq -r .intent)" = "saludo"
test "$(echo "$GREETING" | jq -r .row_count)" = "0"
test "$(echo "$GREETING" | jq -r .sql)" = "null"

echo "== Agente: respuesta natural y tabla =="
ASK=$(curl -fsS -X POST "$BASE_API/api/ask" -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Cuantos sismos se registraron en las ultimas 24 horas?"}')
echo "$ASK" | jq '{answer,answer_provider,provider,validated,row_count}'
test "$(echo "$ASK" | jq -r .row_count)" -gt 0
test -n "$(echo "$ASK" | jq -r .answer)"
if echo "$ASK" | jq -r .answer | grep -q 'id='; then
  echo "La respuesta sigue mostrando filas crudas"
  exit 1
fi

echo "OK: verificacion completa"
