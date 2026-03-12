#!/bin/bash
# Admin Operations for OpenClaw Stack — callable from WhatsApp/Telegram
# Usage: ./admin-ops.sh <command>
#   status          — Full health check (Docker + Gateway + APIs)
#   restart-gateway — Restart the OpenClaw Gateway service
#   restart-docker  — Restart all Docker containers (rebuild)
#   restart-api     — Restart only oc_api container
#   fix-all         — Nuclear option: restart gateway + rebuild all Docker containers

cmd="${1:-status}"

# Node v22 path for openclaw CLI (MUST use v22+)
export PATH="/home/albi_agent/.nvm/versions/node/v22.22.0/bin:$PATH"

# Helper
ok()   { echo "✅ $1"; }
fail() { echo "❌ $1"; }

# Proper gateway restart function (solves the zombie process problem)
restart_gateway() {
  echo "Paso: stop gateway (openclaw gateway stop)..."
  openclaw gateway stop 2>/dev/null || true
  sleep 2
  echo "Paso: start gateway (systemctl start)..."
  sudo -n systemctl start openclaw-gateway 2>/dev/null
  sleep 5
  gw_status=$(sudo -n systemctl is-active openclaw-gateway 2>/dev/null)
  if [[ "$gw_status" == "active" ]]; then
    ok "Gateway reiniciado. PID: $(pgrep -f openclaw-gateway 2>/dev/null)"
  else
    fail "Gateway NO arrancó. Estado: $gw_status"
    sudo -n journalctl -u openclaw-gateway --no-pager -n 5 2>/dev/null
  fi
}

case "$cmd" in

  status)
    echo "🔍 ESTADO COMPLETO DEL SISTEMA"
    echo "=============================="
    echo ""
    echo "📦 Docker Containers:"
    sudo -n docker ps --format "  {{.Names}}: {{.Status}}" 2>/dev/null
    echo ""
    echo "🌐 API Health:"
    for svc in "oc_api:8000" "oc_exporter:8001" "oc_control:8081"; do
      name="${svc%%:*}"
      port="${svc##*:}"
      resp=$(curl -sf --max-time 3 "http://localhost:${port}/health" 2>/dev/null)
      if [[ $? -eq 0 ]]; then
        ok "$name (port $port): $resp"
      else
        fail "$name (port $port): NO RESPONDE"
      fi
    done
    echo ""
    echo "🤖 OpenClaw Gateway:"
    gw_status=$(sudo -n systemctl is-active openclaw-gateway 2>/dev/null)
    if [[ "$gw_status" == "active" ]]; then
      ok "Gateway: active"
    else
      fail "Gateway: $gw_status"
    fi
    echo ""
    echo "📄 Últimos PDFs generados:"
    ls -lt ~/.openclaw/workspace/docs/*.pdf 2>/dev/null | head -3 || echo "  (ninguno)"
    ;;

  restart-gateway)
    echo "🔄 Reiniciando OpenClaw Gateway..."
    restart_gateway
    ;;

  restart-docker)
    echo "🔄 Reiniciando TODOS los contenedores Docker..."
    cd ~/openclawd_stack || exit 1
    sudo -n docker compose restart 2>/dev/null
    sleep 5
    echo ""
    echo "Estado tras reinicio:"
    sudo -n docker ps --format "  {{.Names}}: {{.Status}}" 2>/dev/null
    ok "Docker containers reiniciados."
    ;;

  restart-api)
    echo "🔄 Reiniciando solo oc_api..."
    sudo -n docker restart oc_api 2>/dev/null
    sleep 3
    resp=$(curl -sf --max-time 3 "http://localhost:8000/health" 2>/dev/null)
    if [[ $? -eq 0 ]]; then
      ok "oc_api reiniciado: $resp"
    else
      fail "oc_api no responde tras reinicio"
    fi
    ;;

  fix-all)
    echo "🔧 FIX-ALL: Reiniciando Gateway + Docker (puede tardar ~15s)..."
    echo ""
    echo "Paso 1/2: Gateway..."
    restart_gateway
    echo ""
    echo "Paso 2/2: Docker containers..."
    cd ~/openclawd_stack || exit 1
    sudo -n docker compose restart 2>/dev/null
    sleep 5
    sudo -n docker ps --format "  {{.Names}}: {{.Status}}" 2>/dev/null
    echo ""
    ok "FIX-ALL completado. Todo debería estar operativo."
    ;;

  *)
    echo "Comando desconocido: $cmd"
    echo "Comandos disponibles: status | restart-gateway | restart-docker | restart-api | fix-all"
    exit 1
    ;;
esac
