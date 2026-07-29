#!/usr/bin/env bash
# backup.sh - Automated backup script for FunStuffBarn Dashboard
# Runs via cron daily at 02:00

set -euo pipefail

# Configuración
DEPLOY_DIR="/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard"
BACKUP_ROOT="/Users/javiermaldonadocorreaair/Backups/FunStuffBarn"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
RETENTION_WEEKS=12
RETENTION_MONTHS=12

# Directorios a respaldar
REPORTES_DIR="$DEPLOY_DIR/reportes"
PROMPT_ARCHIVE_DIR="$DEPLOY_DIR/prompt_archive"
DISENOS_ROOT="/Users/javiermaldonadocorreaair/Tienda FunStuffBarn"
LOGS_DIR="$DEPLOY_DIR/logs"
ENV_FILE="$DEPLOY_DIR/.env"

# Crear directorio de backup
BACKUP_DIR="$BACKUP_ROOT/$DATE"
mkdir -p "$BACKUP_DIR"

echo "🚀 Iniciando backup $DATE..."

# Función para log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Backup de reportes
log "📁 Respaldando reportes..."
mkdir -p "$BACKUP_DIR/reportes"
rsync -av --delete "$REPORTES_DIR/" "$BACKUP_DIR/reportes/"

# 2. Backup de prompt archive
log "📁 Respaldando prompt archive..."
mkdir -p "$BACKUP_DIR/prompt_archive"
rsync -av --delete "$PROMPT_ARCHIVE_DIR/" "$BACKUP_DIR/prompt_archive/"

# 3. Backup de diseños (solo estructura, no archivos pesados)
log "📁 Respaldando catálogo de diseños..."
mkdir -p "$BACKUP_DIR/disenos"
rsync -av --delete --include="*/" --include="*.json" --include="*.md" --exclude="*" "$DISENOS_ROOT/" "$BACKUP_DIR/disenos/"

# 4. Backup de logs (últimos 7 días)
log "📁 Respaldando logs recientes..."
mkdir -p "$BACKUP_DIR/logs"
find "$LOGS_DIR" -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/logs/" \;

# 5. Backup de .env (encriptado)
log "🔐 Respaldando configuración..."
if [[ -f "$ENV_FILE" ]]; then
    # Encriptar con gpg (requiere gpg configurado)
    if command -v gpg &> /dev/null; then
        gpg --symmetric --cipher-algo AES256 --output "$BACKUP_DIR/env.gpg" "$ENV_FILE"
        log "✅ .env encriptado en $BACKUP_DIR/env.gpg"
    else
        cp "$ENV_FILE" "$BACKUP_DIR/.env.backup"
        log "⚠️ gpg no disponible, .env copiado sin encriptar"
    fi
fi

# 6. Backup de código (solo archivos fuente)
log "📁 Respaldando código fuente..."
mkdir -p "$BACKUP_DIR/src"
rsync -av --exclude="__pycache__" --exclude="*.pyc" --exclude=".git" --exclude="logs" --exclude="reportes" --exclude="prompt_archive" --exclude="static" --exclude="templates" "$DEPLOY_DIR/" "$BACKUP_DIR/src/"

# 7. Comprimir
log "🗜️ Comprimiendo backup..."
cd "$BACKUP_ROOT"
tar -czf "$BACKUP_DIR.tar.gz" "$DATE"
log "✅ Backup comprimido: $BACKUP_DIR.tar.gz"

# 7. Limpieza por política de retención
log "🧹 Aplicando política de retención..."

# Eliminar backups diarios > 30 días
find "$BACKUP_ROOT" -maxdepth 1 -name "20*" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \;

# Mantener 1 por semana por 12 semanas
find "$BACKUP_ROOT" -maxdepth 1 -name "20*_*" -type f -name "*.tar.gz" | sort -r | tail -n +$((RETENTION_WEEKS + 1)) | xargs -r rm -f

# Mantener 1 por mes por 12 meses
find "$BACKUP_ROOT" -maxdepth 1 -name "20*_*" -type f -name "*.tar.gz" | sort -r | tail -n +$((RETENTION_MONTHS + 1)) | xargs -r rm -f

# 8. Subir a almacenamiento remoto (opcional - rclone)
if command -v rclone &> /dev/null && rclone listremotes | grep -q "gdrive:"; then
    log "☁️ Subiendo a Google Drive..."
    rclone copy "$BACKUP_DIR.tar.gz" "gdrive:FunStuffBarn/Backups/" --progress
    log "☁️ Subida completada"
elif command -v rclone &> /dev/null && rclone listremotes | grep -q "s3:"; then
    log "☁️ Subiendo a S3..."
    rclone copy "$BACKUP_DIR.tar.gz" "s3:funstuffbarn-backups/" --progress
    log "☁️ Subida completada"
else
    log "☁️ rclone no configurado, backup solo local"
fi

# 9. Limpieza local de archivo temporal
rm -rf "$BACKUP_DIR"

log "✅ Backup completado: $BACKUP_DIR.tar.gz"
echo "Tamaño: $(du -h "$BACKUP_ROOT/$DATE.tar.gz" | cut -f1)"