from flask import Flask, request, jsonify
import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
import os
import json
import redis
from datetime import datetime
import uuid
from email_validator import validate_email, EmailNotValidError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

app = Flask(__name__)

# Metrics
EMAIL_SENT_COUNT = Counter('emails_sent_total', 'Total emails sent', ['status'])
EMAIL_SEND_DURATION = Histogram('email_send_duration_seconds', 'Email send duration')

# Redis connection
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# SMTP Configuration
SMTP_CONFIG = {
    'host': os.getenv('SMTP_HOST', 'localhost'),
    'port': int(os.getenv('SMTP_PORT', '1025')),
    'username': os.getenv('SMTP_USER', ''),
    'password': os.getenv('SMTP_PASSWORD', ''),
    'use_tls': os.getenv('SMTP_USE_TLS', 'false').lower() == 'true',
    'from_email': os.getenv('FROM_EMAIL', 'noreply@llm-distribution.local')
}


@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        redis_status = "healthy"
    except:
        redis_status = "unhealthy"

    return jsonify({
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "services": {
            "redis": redis_status,
            "smtp": "configured"
        },
        "smtp_config": {
            "host": SMTP_CONFIG['host'],
            "port": SMTP_CONFIG['port'],
            "use_tls": SMTP_CONFIG['use_tls']
        }
    })


@app.route('/metrics')
def metrics():
    """Prometheus metrics"""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route('/send-package', methods=['POST'])
def send_email_package():
    """Send email package with generated application"""
    try:
        package_data = request.get_json()

        if not package_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['recipient', 'subject', 'body', 'attachments']
        for field in required_fields:
            if field not in package_data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400

        # Validate email
        try:
            valid_email = validate_email(package_data['recipient'])
            recipient_email = valid_email.email
        except EmailNotValidError:
            return jsonify({'success': False, 'error': 'Invalid recipient email'}), 400

        # Generate email ID for tracking
        email_id = str(uuid.uuid4())

        # Send email
        with EMAIL_SEND_DURATION.time():
            result = send_smtp_email(
                recipient=recipient_email,
                subject=package_data['subject'],
                body=package_data['body'],
                attachments=package_data['attachments'],
                headers=package_data.get('headers', {}),
                email_id=email_id
            )

        if result['success']:
            EMAIL_SENT_COUNT.labels(status='success').inc()

            # Store email record in Redis
            email_record = {
                'email_id': email_id,
                'recipient': recipient_email,
                'subject': package_data['subject'],
                'sent_at': datetime.now().isoformat(),
                'status': 'sent',
                'attachments_count': len(package_data['attachments'])
            }

            redis_client.setex(
                f"email:{email_id}",
                86400,  # 24 hours
                json.dumps(email_record)
            )

            return jsonify({
                'success': True,
                'email_id': email_id,
                'message': 'Email sent successfully'
            })
        else:
            EMAIL_SENT_COUNT.labels(status='error').inc()
            return jsonify(result), 500

    except Exception as e:
        EMAIL_SENT_COUNT.labels(status='error').inc()
        return jsonify({'success': False, 'error': str(e)}), 500


def send_smtp_email(recipient, subject, body, attachments, headers, email_id):
    """Send email via SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_CONFIG['from_email']
        msg['To'] = recipient
        msg['Subject'] = subject

        # Add custom headers
        for key, value in headers.items():
            msg[key] = value

        msg['Message-ID'] = f"<{email_id}@llm-distribution.local>"

        # Add body
        if isinstance(body, dict):
            if 'text' in body:
                msg.attach(MIMEText(body['text'], 'plain', 'utf-8'))
            if 'html' in body:
                msg.attach(MIMEText(body['html'], 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(str(body), 'plain', 'utf-8'))

        # Add attachments
        for attachment in attachments:
            part = MIMEBase('application', 'octet-stream')

            if attachment.get('encoding') == 'base64':
                attachment_data = base64.b64decode(attachment['content'])
            else:
                attachment_data = attachment['content'].encode('utf-8')

            part.set_payload(attachment_data)
            encoders.encode_base64(part)

            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment["filename"]}'
            )

            if 'content_type' in attachment:
                part.add_header('Content-Type', attachment['content_type'])

            msg.attach(part)

        # Send email
        context = ssl.create_default_context()

        with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as server:
            if SMTP_CONFIG['use_tls']:
                server.starttls(context=context)

            if SMTP_CONFIG['username'] and SMTP_CONFIG['password']:
                server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])

            server.send_message(msg)

        return {'success': True, 'email_id': email_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.route('/email-status/<email_id>')
def get_email_status(email_id):
    """Get email delivery status"""
    try:
        email_record = redis_client.get(f"email:{email_id}")

        if not email_record:
            return jsonify({'error': 'Email not found'}), 404

        data = json.loads(email_record)
        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/send-test', methods=['POST'])
def send_test_email():
    """Send test email"""
    try:
        data = request.get_json()
        recipient = data.get('recipient')

        if not recipient:
            return jsonify({'error': 'Recipient email required'}), 400

        # Validate email
        try:
            valid_email = validate_email(recipient)
            recipient_email = valid_email.email
        except EmailNotValidError:
            return jsonify({'error': 'Invalid email address'}), 400

        # Send simple test email
        test_package = {
            'recipient': recipient_email,
            'subject': 'Test Email from LLM Distribution System',
            'body': {
                'text': 'This is a test email from the LLM Email Distribution System. If you received this, the SMTP configuration is working correctly.',
                'html': '<p>This is a <strong>test email</strong> from the LLM Email Distribution System.</p><p>If you received this, the SMTP configuration is working correctly.</p>'
            },
            'attachments': [],
            'headers': {
                'X-Test-Email': 'true'
            }
        }

        return send_email_package()

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

