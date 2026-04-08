#!/bin/bash
# 人脸识别系统数据备份脚本
BACKUP_DIR="/app/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

mkdir -p $BACKUP_DIR

echo "[$TIMESTAMP] 开始备份..."

# 备份数据库
if [ -f "/app/data/face_scan.db" ]; then
    cp /app/data/face_scan.db "$BACKUP_DIR/db_${TIMESTAMP}.db"
    echo "数据库备份完成"
fi

# 打包人脸数据
if [ -d "/app/data/faces" ]; then
    tar czf "$BACKUP_DIR/faces_${TIMESTAMP}.tar.gz" -C /app/data faces/
    echo "人脸数据备份完成"
fi

# 打包编码数据
if [ -d "/app/data/faces/encodings" ]; then
    tar czf "$BACKUP_DIR/encodings_${TIMESTAMP}.tar.gz" -C /app/data faces/encodings/
    echo "编码数据备份完成"
fi

# 清理过期备份
find $BACKUP_DIR -name "*.db" -mtime +$KEEP_DAYS -delete 2>/dev/null
find $BACKUP_DIR -name "*.tar.gz" -mtime +$KEEP_DAYS -delete 2>/dev/null

echo "[$TIMESTAMP] 备份完成。当前备份数: $(ls -1 $BACKUP_DIR 2>/dev/null | wc -l)"
