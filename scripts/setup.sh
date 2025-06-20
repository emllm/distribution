#!/bin/bash

echo "🚀 Setting up LLM Email Distribution System"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration before continuing"
    exit 1
fi

# Create required directories
echo "📁 Creating required directories..."
mkdir -p templates generated email-templates attachments monitoring/grafana

# Pull Ollama model for local LLM
echo "🤖 Pulling Ollama models (this may take a while)..."
docker-compose up -d ollama
sleep 10
docker-compose exec ollama ollama pull codellama:7b-instruct
docker-compose exec ollama ollama pull mistral:7b-instruct

# Start all services
echo "🐳 Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Health checks
echo "🔍 Checking service health..."

# Check LLM Generator
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ LLM Generator is healthy"
else
    echo "❌ LLM Generator is not responding"
fi

# Check SMTP Service
if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ SMTP Service is healthy"
else
    echo "❌ SMTP Service is not responding"
fi

# Check Webhook Receiver
if curl -f http://localhost:9000/health > /dev/null 2>&1; then
    echo "✅ Webhook Receiver is healthy"
else
    echo "❌ Webhook Receiver is not responding"
fi

echo ""
echo "🎉 Setup complete! Services are running:"
echo "   LLM Generator API: http://localhost:8000"
echo "   SMTP Service: http://localhost:5000"
echo "   Webhook Receiver: http://localhost:9000"
echo "   MailHog Web UI: http://localhost:8025"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana: http://localhost:3000 (admin/admin123)"
echo ""
echo "📧 Test email generation:"
echo "   curl -X POST http://localhost:9000/test-generation"
echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f llm-generator"
