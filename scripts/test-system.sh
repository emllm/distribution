#!/bin/bash

echo "🧪 Testing LLM Email Distribution System"

API_TOKEN=${API_TOKEN:-"dev-token-123"}
BASE_URL="http://localhost:8000"

# Test 1: Health Check
echo "1️⃣ Testing health endpoints..."
curl -s http://localhost:8000/health | jq '.'
curl -s http://localhost:5000/health | jq '.'
curl -s http://localhost:9000/health | jq '.'

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
REQUEST_ID=$(echo "$GENERATION_RESPONSE" | jq -r '.request_id')

echo ""

# Test 3: Check Status
echo "3️⃣ Checking generation status..."
sleep 5
curl -s "$BASE_URL/status/$REQUEST_ID" \
  -H "Authorization: Bearer $API_TOKEN" | jq '.'

echo ""

# Test 4: Webhook Trigger
echo "4️⃣ Testing webhook trigger..."
curl -s -X POST http://localhost:9000/webhook/generate \
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
curl -s -X POST http://localhost:5000/send-test \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "smtp-test@example.com"
  }' | jq '.'

echo ""
echo "✅ Testing complete!"
echo "📧 Check MailHog at http://localhost:8025 to see sent emails"
echo "📊 Monitor metrics at http://localhost:9090"

