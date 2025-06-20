#!/bin/bash

# Source environment variables from the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

echo "🧪 Testing LLM Email Distribution System with Updated Ports"

API_TOKEN=${API_TOKEN:-$API_TOKEN}
if [ -z "$API_TOKEN" ]; then
    echo "❌ API_TOKEN is not set. Please set it in the .env file"
    exit 1
fi

BASE_URL="http://localhost:8080"  # LLM Generator port
SMTP_URL="http://localhost:5001"  # SMTP Service port
WEBHOOK_URL="http://localhost:9001"  # Webhook Receiver port

# Test 1: Health Check
echo "1️⃣ Testing health endpoints..."
# Check LLM Generator health
curl -s $BASE_URL/health | jq '.' || echo "LLM Generator health check failed"

# Check SMTP Service health
curl -s $SMTP_URL/health | jq '.' || echo "SMTP Service health check failed"

# Check Webhook Receiver health
curl -s $WEBHOOK_URL/health | jq '.' || echo "Webhook Receiver health check failed"

echo ""

# Test 2: Generate Application via API
echo "2️⃣ Testing direct API generation..."
GENERATION_RESPONSE=$(curl -s -X POST "$BASE_URL/generate" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "app_type": "dashboard",
    "description": "Simple metrics dashboard with charts",
    "recipient_email": "test@example.com",
    "tech_stack": ["python", "fastapi", "html"],
    "features": ["responsive_design", "charts"],
    "metadata": {
      "test": true,
      "urgency": "high"
    }
  }')

echo "$GENERATION_RESPONSE" | jq '.'
REQUEST_ID=$(echo "$GENERATION_RESPONSE" | jq -r '.request_id' 2>/dev/null)

if [ -n "$REQUEST_ID" ] && [ "$REQUEST_ID" != "null" ]; then
  echo "✅ Request ID: $REQUEST_ID"
  
  # Test 3: Check Status
  echo ""
  echo "3️⃣ Checking generation status..."
  sleep 5
  curl -s "$BASE_URL/status/$REQUEST_ID" \
    -H "Authorization: Bearer $API_TOKEN" | jq '.'
else
  echo "❌ Failed to get request ID from the response"
fi

echo ""

# Test 4: Webhook Trigger
echo "4️⃣ Testing webhook trigger..."
curl -s -X POST $WEBHOOK_URL/webhook/generate \
  -H "Content-Type: application/json" \
  -d '{
    "app_type": "api",
    "description": "REST API with CRUD operations",
    "recipient_email": "webhook-test@example.com",
    "tech_stack": ["python", "fastapi"],
    "features": ["authentication", "database"],
    "callback_url": "http://webhook-receiver:9000/webhook/status"
  }' | jq '.'

echo ""

# Test 5: Send Test Email
echo "5️⃣ Testing SMTP service..."
curl -s -X POST $SMTP_URL/send-test \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "smtp-test@example.com"
  }' | jq '.'

echo ""
echo "✅ Testing complete!"
echo "📧 Check MailHog at http://localhost:8026 to see sent emails"
echo "🔍 Check container logs with: docker-compose logs -f"
