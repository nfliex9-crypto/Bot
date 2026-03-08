#!/bin/bash
set -e

echo "Starting AI Trading System..."

if [ ! -f backend/.env ]; then
    echo "Creating .env from example..."
    cp backend/.env.example backend/.env
fi

echo "Starting Docker containers..."
docker-compose up -d --build

echo "Waiting for database..."
sleep 10

echo "Running migrations..."
docker-compose exec backend alembic upgrade head

echo ""
echo "AI Trading System is running!"
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "  DB:   localhost:5432"
echo ""
