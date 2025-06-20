from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
import asyncio
import json
import os
import uuid
from datetime import datetime
import redis
import httpx
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# Import LLM providers
from llm_providers import OpenAIProvider, AnthropicProvider, OllamaProvider
from code_generator import CodeGenerator
from email_packager import EmailPackager

app = FastAPI(title="LLM Email Distribution Service", version="1.0.0")

# Metrics
REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
GENERATION_COUNT = Counter('code_generations_total', 'Total code generations', ['provider', 'status'])

# Redis connection
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Security
security = HTTPBearer()


class GenerationRequest(BaseModel):
    app_type: str
    description: str
    requirements: List[str] = []
    recipient_email: str
    tech_stack: List[str] = ["python", "fastapi"]
    deployment_target: str = "docker"
    features: List[str] = []
    metadata: Dict[str, Any] = {}
    webhook_url: Optional[str] = None


class GenerationResponse(BaseModel):
    request_id: str
    status: str
    message: str
    estimated_completion: Optional[str] = None


# Initialize LLM provider
def get_llm_provider():
    provider_type = os.getenv('LLM_PROVIDER', 'openai').lower()

    if provider_type == 'openai':
        return OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY'))
    elif provider_type == 'anthropic':
        return AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'))
    elif provider_type == 'ollama':
        return OllamaProvider(base_url=os.getenv('OLLAMA_URL', 'http://localhost:11434'))
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_type}")


llm_provider = get_llm_provider()
code_generator = CodeGenerator(llm_provider)
email_packager = EmailPackager()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Simple token verification - in production use proper JWT validation
    expected_token = os.getenv('API_TOKEN', 'dev-token-123')
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        redis_client.ping()
        redis_status = "healthy"
    except:
        redis_status = "unhealthy"

    # Test LLM provider
    try:
        llm_status = await llm_provider.test_connection()
    except:
        llm_status = "unhealthy"

    return {
        "status": "healthy" if redis_status == "healthy" and llm_status == "healthy" else "degraded",
        "services": {
            "redis": redis_status,
            "llm_provider": llm_status
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/generate", response_model=GenerationResponse)
async def generate_application(
        request: GenerationRequest,
        background_tasks: BackgroundTasks,
        token: str = Depends(verify_token)
):
    """Generate application and send via email"""
    REQUEST_COUNT.labels(method="POST", endpoint="/generate").inc()

    request_id = str(uuid.uuid4())

    # Store request in Redis
    request_data = request.dict()
    request_data['request_id'] = request_id
    request_data['status'] = 'queued'
    request_data['created_at'] = datetime.now().isoformat()

    redis_client.setex(
        f"generation:{request_id}",
        3600,  # 1 hour TTL
        json.dumps(request_data)
    )

    # Queue background generation task
    background_tasks.add_task(
        process_generation_request,
        request_id,
        request_data
    )

    return GenerationResponse(
        request_id=request_id,
        status="queued",
        message="Generation request queued successfully",
        estimated_completion="2-5 minutes"
    )


@app.get("/status/{request_id}")
async def get_generation_status(request_id: str, token: str = Depends(verify_token)):
    """Get generation status"""
    request_data = redis_client.get(f"generation:{request_id}")

    if not request_data:
        raise HTTPException(status_code=404, detail="Request not found")

    data = json.loads(request_data)
    return {
        "request_id": request_id,
        "status": data.get('status'),
        "created_at": data.get('created_at'),
        "completed_at": data.get('completed_at'),
        "error": data.get('error'),
        "email_sent": data.get('email_sent', False)
    }


async def process_generation_request(request_id: str, request_data: Dict[str, Any]):
    """Background task to process generation request"""
    try:
        # Update status to processing
        request_data['status'] = 'processing'
        request_data['started_at'] = datetime.now().isoformat()
        redis_client.setex(f"generation:{request_id}", 3600, json.dumps(request_data))

        # Generate code using LLM
        generation_result = await code_generator.generate_application(
            app_type=request_data['app_type'],
            description=request_data['description'],
            requirements=request_data['requirements'],
            tech_stack=request_data['tech_stack'],
            features=request_data['features']
        )

        if not generation_result['success']:
            raise Exception(f"Code generation failed: {generation_result['error']}")

        # Package into email format
        email_package = await email_packager.create_package(
            request_id=request_id,
            generation_result=generation_result,
            metadata=request_data['metadata'],
            recipient=request_data['recipient_email']
        )

        # Send email via SMTP service
        smtp_response = await send_email_package(email_package)

        if not smtp_response['success']:
            raise Exception(f"Email sending failed: {smtp_response['error']}")

        # Update status to completed
        request_data['status'] = 'completed'
        request_data['completed_at'] = datetime.now().isoformat()
        request_data['email_sent'] = True
        request_data['email_id'] = smtp_response.get('email_id')

        GENERATION_COUNT.labels(provider=llm_provider.__class__.__name__, status='success').inc()

        # Send webhook notification if provided
        if request_data.get('webhook_url'):
            await send_webhook_notification(request_data['webhook_url'], {
                'request_id': request_id,
                'status': 'completed',
                'email_sent': True,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        # Update status to failed
        request_data['status'] = 'failed'
        request_data['error'] = str(e)
        request_data['failed_at'] = datetime.now().isoformat()

        GENERATION_COUNT.labels(provider=llm_provider.__class__.__name__, status='error').inc()

        # Send webhook notification about failure
        if request_data.get('webhook_url'):
            await send_webhook_notification(request_data['webhook_url'], {
                'request_id': request_id,
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    finally:
        # Always update Redis with final status
        redis_client.setex(f"generation:{request_id}", 3600, json.dumps(request_data))


async def send_email_package(email_package: Dict[str, Any]) -> Dict[str, Any]:
    """Send email package via SMTP service"""
    smtp_service_url = os.getenv('SMTP_SERVICE_URL', 'http://localhost:5000')

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{smtp_service_url}/send-package",
            json=email_package,
            timeout=30.0
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {
                'success': False,
                'error': f"SMTP service error: {response.status_code} - {response.text}"
            }


async def send_webhook_notification(webhook_url: str, data: Dict[str, Any]):
    """Send webhook notification"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                webhook_url,
                json=data,
                timeout=10.0,
                headers={'Content-Type': 'application/json'}
            )
    except Exception as e:
        print(f"Webhook notification failed: {e}")


@app.post("/webhook/test")
async def webhook_test_endpoint(data: Dict[str, Any]):
    """Test webhook endpoint for development"""
    print(f"Webhook received: {json.dumps(data, indent=2)}")
    return {"status": "received", "data": data}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

