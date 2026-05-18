#!/bin/sh
set -e

cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    nginx -s quit 2>/dev/null || true
    wait
    exit 0
}

trap cleanup TERM INT

export PORT=${PORT:-8080}

sed -i "s/\${PORT}/$PORT/g" /etc/nginx/nginx.conf

cd /app/backend
gunicorn main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 120 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile - \
    --error-logfile - &
BACKEND_PID=$!

cd /app/frontend
PORT=3000 node server.js &
FRONTEND_PID=$!

sleep 1

nginx -g 'daemon off;'
