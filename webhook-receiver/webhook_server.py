from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

LLM_SERVICE_URL = os.getenv('LLM_SERVICE_URL', 'http://localhost:8000')

@app.route('/webhook/generate', methods=['POST'])
def handle_generation_webhook():
    """Handle webhook to trigger code generation"""
    try:
        # Parse webhook data
        webhook_data = request.get_json()

        print(f"[{datetime.now()}] Received webhook: {json.dumps(webhook_data, indent=2)}")

        # Extract generation parameters
        generation_request = {
            'app_type': webhook_data.get('app_type', 'web_application'),
            'description': webhook_data.get('description', 'Generated application'),
            'requirements': webhook_data.get('requirements', []),
            'recipient_email': webhook_data.get('recipient_email'),
            'tech_stack': webhook_data.get('tech_stack', ['python', 'fastapi']),
            'deployment_target': webhook_data.get('deployment_target', 'docker'),
            'features': webhook_data.get('features', []),
            'metadata': webhook_data.get('metadata', {}),
            'webhook_url': webhook_data.get('callback_url')
        }

        # Validate required fields
        if not generation_request['recipient_email']:
            return jsonify({'error': 'recipient_email is required'}), 400

        # Forward to LLM generation service
        response = requests.post(
            f"{LLM_SERVICE_URL}/generate",
            json=generation_request,
            headers={
                'Authorization': f'Bearer {os.getenv("API_TOKEN", "dev-token-123")}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print(f"[{datetime.now()}] Generation queued: {result['request_id']}")

            return jsonify({
                'success': True,
                'request_id': result['request_id'],
                'message': 'Code generation queued successfully',
                'status_url': f"{LLM_SERVICE_URL}/status/{result['request_id']}"
            })
        else:
            error_msg = f"LLM service error: {response.status_code} - {response.text}"
            print(f"[{datetime.now()}] Error: {error_msg}")
            return jsonify({'error': error_msg}), response.status_code

    except Exception as e:
        error_msg = f"Webhook processing error: {str(e)}"
        print(f"[{datetime.now()}] Error: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/webhook/status', methods=['POST'])
def handle_status_webhook():
    """Handle status update webhooks from LLM service"""
    try:
        status_data = request.get_json()
        print(f"[{datetime.now()}] Status update: {json.dumps(status_data, indent=2)}")

        # Here you could forward to external systems, log to database, etc.
        # For demo purposes, we just log and acknowledge

        return jsonify({'success': True, 'message': 'Status received'})

    except Exception as e:
        print(f"[{datetime.now()}] Status webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'llm_service_url': LLM_SERVICE_URL
    })

@app.route('/test-generation', methods=['POST'])
def test_generation():
    """Test endpoint for manual generation requests"""
    test_request = {
        'app_type': 'dashboard',
        'description': 'Simple web dashboard with metrics and charts',
        'recipient_email': 'test@example.com',
        'tech_stack': ['python', 'fastapi', 'html'],
        'features': ['responsive_design', 'charts', 'real_time_updates'],
        'metadata': {
            'urgency': 'normal',
            'complexity': 'medium'
        }
    }

    # Trigger generation
    return handle_generation_webhook()

if __name__ == '__main__':
    print(f"Starting Webhook Receiver on port 9000")
    print(f"LLM Service URL: {LLM_SERVICE_URL}")
    app.run(host='0.0.0.0', port=9000, debug=True)

