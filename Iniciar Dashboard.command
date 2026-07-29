#!/usr/bin/env bash
# Iniciar FunStuffBarn Dashboard - Doble clic para ejecutar

cd "$(dirname "$0")"

echo "🚀 Iniciando FunStuffBarn Dashboard..."
echo ""

# Verificar si ya está corriendo
if lsof -ti:8080 >/dev/null 2>&1; then
    echo "⚠️ El dashboard ya está corriendo en puerto 8080"
    echo "   Abre: http://localhost:8080"
    read -p "Presiona Enter para cerrar..."
    exit 0
fi

# Verificar dependencias
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no encontrado"
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

# Verificar si existe main.py
if [ ! -f "main.py" ]; then
    echo "❌ No se encuentra main.py en esta carpeta"
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

# Instalar dependencias si no existen
if ! python3 -c "import fastapi, uvicorn, jinja2" 2>/dev/null; then
    echo "📦 Instalando dependencias..."
    pip3 install -q fastapi uvicorn jinja2 python-multipart python-docx prometheus-client python-json-logger python-dotenv
fi

echo "🚀 Iniciando servidor en http://localhost:8080"
echo "   Presiona Ctrl+C para detener"
echo ""

# Iniciar servidor
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info