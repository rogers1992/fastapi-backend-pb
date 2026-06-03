#!/bin/bash

echo "🚀 Starting Paraiso Biker Backend..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Start database
echo "📦 Starting PostgreSQL database..."
docker-compose up -d

echo "⏳ Waiting for database to be ready..."
sleep 10

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Generate and import seed data
echo "🌱 Generating seed data..."
python scripts/seed_data.py

echo "📥 Importing seed data into database..."
python scripts/import_seed_data.py

# Start API server
echo "🚀 Starting API server..."
echo ""
echo "✅ Backend is ready!"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "🔑 Default login: admin / admin123"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
