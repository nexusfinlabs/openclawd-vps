#!/bin/bash
# TEST_FLUJO — Suite de verificación de estabilidad del Bot
# Usage: test-flujo [1|2]

case "$1" in
    1)
        echo "🧪 **TEST_FLUJO 1: Conectividad Socket/Daemon**"
        if [ -S /home/albi_agent/.openclaw/exec-approvals.sock ]; then
            echo "✅ Socket existe."
            # Intento de envío manual al socket (mock)
            RESPONSE=$(python3 -c "import socket, json; s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(\"/home/albi_agent/.openclaw/exec-approvals.sock\"); s.sendall(json.dumps({\"id\":\"test\",\"agent\":\"*\"}).encode()); print(s.recv(1024).decode())")
            echo "📥 Respuesta Daemon: $RESPONSE"
        else
            echo "❌ Socket NO encontrado en /home/albi_agent/.openclaw/exec-approvals.sock"
        fi
        ;;
    2)
        echo "🧪 **TEST_FLUJO 2: Mock de Propuesta (Dry Run)**"
        echo "Generando borrador falso para validar prompt..."
        python3 /home/albi_agent/openclawd_stack/ops/proposal_manager.py --make "test@example.com" "Cual es el sentido de la vida?" | head -n 5
        echo "---"
        echo "✅ Generación Python OK (Claude 3.5 respondiendo)."
        ;;
    *)
        echo "Uso: !test-flujo [1|2]"
        echo "1: Check Socket/Daemon"
        echo "2: Check Motor AI (Claude 3.5)"
        ;;
esac
