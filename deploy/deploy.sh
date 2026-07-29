#!/usr/bin/env bash
# deploy.sh - Deploy script for FunStuffBarn Dashboard (macOS)

set -euo pipefail

DEPLOY_DIR="/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard"
PLIST_DIR="/Library/LaunchDaemons"
DASHBOARD_PLIST="com.funstuffbarn.dashboard.plist"
CADDY_PLIST="com.funstuffbarn.caddy.plist"

echo "🚀 Desplegando FunStuffBarn Dashboard..."

# 1. Verificar archivos necesarios
if [[ ! -f "$DEPLOY_DIR/main.py" ]]; then
    echo "❌ No se encuentra main.py en $DEPLOY_DIR"
    exit 1
fi

# 2. Instalar dependencias
echo "📦 Instalando dependencias..."
cd "$DEPLOY_DIR"
python3 -m pip install -q fastapi uvicorn jinja2 python-multipart python-docx prometheus-client python-json-logger

# 3. Crear plist para Dashboard
echo "📝 Creando LaunchDaemon para Dashboard..."
cat > "/tmp/$DASHBOARD_PLIST" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.funstuffbarn.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8080</string>
        <string>--log-level</string>
        <string>info</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard/logs/salida.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard/logs/errores.log</string>
    <key>UserName</key>
    <string>javiermaldonadocorreaair</string>
    <key>GroupName</key>
    <string>staff</string>
</dict>
</plist>
PLIST_EOF

sudo cp "/tmp/$DASHBOARD_PLIST" "$PLIST_DIR/"

# 4. Crear plist para Caddy (opcional - requiere caddy instalado)
echo "📝 Creando LaunchDaemon para Caddy (opcional)..."
cat > "/tmp/$CADDY_PLIST" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.funstuffbarn.caddy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/caddy</string>
        <string>run</string>
        <string>--config</string>
        <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard/Caddyfile</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard/logs/caddy.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard/logs/caddy_error.log</string>
    <key>UserName</key>
    <string>javiermaldonadocorreaair</string>
    <key>GroupName</key>
    <string>staff</string>
</dict>
</plist>
PLIST_EOF

# 5. Instalar plists
echo "📋 Instalando LaunchDaemons..."
sudo cp "/tmp/$DASHBOARD_PLIST" "$PLIST_DIR/"
sudo cp "/tmp/$CADDY_PLIST" "$PLIST_DIR/"

# 6. Cargar servicios
echo "🔄 Cargando servicios..."
sudo launchctl unload "$PLIST_DIR/com.funstuffbarn.dashboard.plist" 2>/dev/null || true
sudo launchctl load "$PLIST_DIR/com.funstuffbarn.dashboard.plist"

# Caddy solo si está instalado
if command -v caddy &> /dev/null; then
    sudo launchctl unload "$PLIST_DIR/com.funstuffbarn.caddy.plist" 2>/dev/null || true
    sudo launchctl load "$PLIST_DIR/com.funstuffbarn.caddy.plist"
    echo "✅ Caddy cargado"
else
    echo "⚠️ Caddy no instalado (opcional: brew install caddy)"
fi

# 6. Crear directorio de logs
mkdir -p "/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard/logs"

# 7. Verificar
echo "✅ Verificando servicios..."
sleep 3

if launchctl list | grep -q "com.funstuffbarn.dashboard"; then
    echo "✅ Dashboard corriendo (PID: $(launchctl list | grep com.funstuffbarn.dashboard | awk '{print $1}'))"
else
    echo "❌ Dashboard no iniciado"
fi

# 7. Health check
echo "🏥 Health check..."
sleep 2
if curl -sf http://localhost:8080/ >/dev/null; then
    echo "✅ Dashboard respondiendo en http://localhost:8080"
else
    echo "❌ Dashboard no responde"
fi

echo ""
echo "✅ Deploy completado!"
echo "🌐 Dashboard: http://localhost:8080"
echo "📊 Logs: tail -f /Users/javiermaldonadocorreaair/Tienda\ FunStuffBarn/dashboard/logs/salida.log"