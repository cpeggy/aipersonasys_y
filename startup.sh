#!/bin/bash

echo "創建必要的目錄結構..."

# 創建主要目錄
mkdir -p uploads
mkdir -p outputs/personas/csv
mkdir -p outputs/personas/csv2
mkdir -p outputs/personas/md

echo "目錄結構創建完成"

# 設置權限
chmod -R 755 uploads
chmod -R 755 outputs

echo "權限設置完成"

# 啟動應用
echo "啟動應用程式..."
exec gunicorn app:app --workers=1 --threads=2 --worker-class=gthread