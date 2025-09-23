# 📡 API Reference

## Overview

The WhatsApp LLM Chatbot API provides a comprehensive REST interface for managing conversations, processing messages, and administering the chatbot system. Built with FastAPI, it offers automatic OpenAPI documentation, type validation, and high performance.

## Base URL
```
Production: https://api.yourdomain.com/v1
Development: http://localhost:8014/v1
```

## Authentication

### Bearer Token Authentication
All API requests require authentication using Bearer tokens.

```bash
curl -H "Authorization: Bearer your_api_token" \
     https://api.yourdomain.com/v1/conversations
```

### API Token Generation
```python
from src.core.security import create_api_token

# Generate token for user
token = create_api_token(user_id="user123", expires_in_days=30)
print(f"API Token: {token}")
```

## Core API Endpoints

### Conversations

#### List Conversations
```http
GET /v1/conversations
```

**Parameters:**
- `limit` (integer, optional): Maximum number of conversations to return (default: 50, max: 100)
- `offset` (integer, optional): Number of conversations to skip (default: 0)
- `chat_id` (string, optional): Filter by WhatsApp chat ID
- `user_id` (string, optional): Filter by user ID
- `start_date` (string, optional): Filter conversations after this date (ISO 8601)
- `end_date` (string, optional): Filter conversations before this date (ISO 8601)

**Response:**
```json
{
  "conversations": [
    {
      "id": "conv_123456",
      "chat_id": "573107601252@c.us",
      "user_id": "user123",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T14:45:00Z",
      "message_count": 25,
      "last_message": {
        "content": "Thank you for your help!",
        "timestamp": "2024-01-15T14:45:00Z",
        "sender_type": "user"
      },
      "metadata": {
        "priority": "high",
        "tags": ["support", "urgent"]
      }
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

**Example:**
```bash
curl -H "Authorization: Bearer your_token" \
     "https://api.yourdomain.com/v1/conversations?limit=10&chat_id=573107601252@c.us"
```

#### Get Conversation Details
```http
GET /v1/conversations/{conversation_id}
```

**Response:**
```json
{
  "id": "conv_123456",
  "chat_id": "573107601252@c.us",
  "user_id": "user123",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T14:45:00Z",
  "messages": [
    {
      "id": "msg_789",
      "content": "Hello, I need help with my order",
      "timestamp": "2024-01-15T10:30:00Z",
      "sender_type": "user",
      "metadata": {
        "message_type": "text",
        "delivery_status": "delivered"
      }
    },
    {
      "id": "msg_790",
      "content": "I'd be happy to help you with your order. Could you please provide your order number?",
      "timestamp": "2024-01-15T10:30:15Z",
      "sender_type": "bot",
      "metadata": {
        "confidence_score": 0.95,
        "processing_time_ms": 1250
      }
    }
  ],
  "summary": {
    "total_messages": 25,
    "user_messages": 12,
    "bot_messages": 13,
    "average_response_time": 8.5,
    "sentiment_score": 0.75
  }
}
```

#### Create Conversation
```http
POST /v1/conversations
```

**Request Body:**
```json
{
  "chat_id": "573107601252@c.us",
  "user_id": "user123",
  "initial_message": "Hello, I need assistance",
  "metadata": {
    "source": "whatsapp",
    "priority": "normal",
    "tags": ["general"]
  }
}
```

**Response:**
```json
{
  "id": "conv_123456",
  "chat_id": "573107601252@c.us",
  "user_id": "user123",
  "created_at": "2024-01-15T10:30:00Z",
  "status": "active"
}
```

#### Update Conversation
```http
PATCH /v1/conversations/{conversation_id}
```

**Request Body:**
```json
{
  "metadata": {
    "priority": "high",
    "tags": ["urgent", "escalated"]
  },
  "status": "escalated"
}
```

### Messages

#### Send Message
```http
POST /v1/messages
```

**Request Body:**
```json
{
  "chat_id": "573107601252@c.us",
  "content": "This is a test message",
  "priority": 3,
  "metadata": {
    "message_type": "text",
    "correlation_id": "req_123"
  }
}
```

**Response:**
```json
{
  "message_id": "msg_123456",
  "status": "queued",
  "estimated_delivery": "2024-01-15T10:30:30Z",
  "correlation_id": "req_123"
}
```

#### Get Message History
```http
GET /v1/conversations/{conversation_id}/messages
```

**Parameters:**
- `limit` (integer, optional): Maximum messages to return (default: 50)
- `before` (string, optional): Get messages before this timestamp (ISO 8601)
- `after` (string, optional): Get messages after this timestamp (ISO 8601)
- `sender_type` (string, optional): Filter by sender type ("user" or "bot")

**Response:**
```json
{
  "messages": [
    {
      "id": "msg_123",
      "conversation_id": "conv_456",
      "content": "Hello, how can I help you?",
      "timestamp": "2024-01-15T10:30:00Z",
      "sender_type": "bot",
      "metadata": {
        "confidence_score": 0.92,
        "processing_time_ms": 850,
        "model_used": "gpt-4-turbo"
      }
    }
  ],
  "total": 25,
  "has_more": true,
  "next_cursor": "2024-01-15T10:29:00Z"
}
```

#### Message Webhook
```http
POST /v1/webhooks/whatsapp
```

**Headers:**
```
X-Hub-Signature-256: sha256=signature_hash
Content-Type: application/json
```

**Request Body:**
```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "your_business_id",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "573107601252",
              "phone_number_id": "your_phone_number_id"
            },
            "contacts": [
              {
                "profile": {
                  "name": "John Doe"
                },
                "wa_id": "573107601252"
              }
            ],
            "messages": [
              {
                "id": "message_id",
                "from": "573107601252",
                "timestamp": "1640995200",
                "text": {
                  "body": "Hello, I need help"
                },
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

**Response:**
```json
{
  "status": "processed",
  "message_id": "msg_123456",
  "response_queued": true
}
```

### Analytics & Reporting

#### Get Conversation Analytics
```http
GET /v1/analytics/conversations
```

**Parameters:**
- `start_date` (string, required): Start date for analytics (ISO 8601)
- `end_date` (string, required): End date for analytics (ISO 8601)
- `group_by` (string, optional): Group results by ("day", "week", "month")

**Response:**
```json
{
  "period": {
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z"
  },
  "metrics": {
    "total_conversations": 1250,
    "total_messages": 8750,
    "average_messages_per_conversation": 7.0,
    "average_response_time_seconds": 12.5,
    "user_satisfaction_score": 4.2,
    "resolution_rate": 0.85
  },
  "trends": [
    {
      "date": "2024-01-01",
      "conversations": 45,
      "messages": 315,
      "average_response_time": 11.2
    }
  ]
}
```

#### Get Performance Metrics
```http
GET /v1/analytics/performance
```

**Response:**
```json
{
  "system_metrics": {
    "uptime_percentage": 99.9,
    "average_response_time_ms": 245,
    "error_rate": 0.02,
    "throughput_messages_per_minute": 150
  },
  "model_performance": {
    "gpt4_turbo": {
      "usage_count": 1250,
      "average_confidence": 0.89,
      "average_processing_time_ms": 1250,
      "error_rate": 0.01
    },
    "gpt3_5_turbo": {
      "usage_count": 890,
      "average_confidence": 0.76,
      "average_processing_time_ms": 850,
      "error_rate": 0.03
    }
  },
  "infrastructure_metrics": {
    "cpu_utilization": 65.5,
    "memory_utilization": 72.3,
    "disk_usage_gb": 45.2,
    "network_throughput_mbps": 25.8
  }
}
```

### Administration

#### System Health Check
```http
GET /v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": {
      "status": "healthy",
      "response_time_ms": 12,
      "connection_pool_size": 10,
      "active_connections": 3
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 2,
      "memory_usage_mb": 45,
      "connected_clients": 12
    },
    "whatsapp_api": {
      "status": "healthy",
      "response_time_ms": 150,
      "rate_limit_remaining": 95
    },
    "openai_api": {
      "status": "healthy",
      "response_time_ms": 200,
      "tokens_used_today": 125000,
      "rate_limit_remaining": 80
    }
  }
}
```

#### Get System Configuration
```http
GET /v1/admin/config
```

**Response:**
```json
{
  "environment": "production",
  "version": "1.0.0",
  "features": {
    "rag_enabled": true,
    "sentiment_analysis": true,
    "auto_escalation": true,
    "multilingual_support": true
  },
  "limits": {
    "max_conversation_length": 1000,
    "max_message_length": 4096,
    "rate_limit_per_minute": 60,
    "max_file_size_mb": 10
  },
  "integrations": {
    "whatsapp_business_api": {
      "status": "connected",
      "webhook_url": "https://api.yourdomain.com/v1/webhooks/whatsapp"
    },
    "openai": {
      "status": "connected",
      "models": ["gpt-4-turbo", "gpt-3.5-turbo"],
      "rate_limit": 1000
    }
  }
}
```

#### Update System Settings
```http
PATCH /v1/admin/settings
```

**Request Body:**
```json
{
  "features": {
    "sentiment_analysis": false,
    "auto_escalation": true
  },
  "limits": {
    "rate_limit_per_minute": 100
  }
}
```

## Error Handling

### Standard Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "chat_id",
      "reason": "Invalid WhatsApp ID format",
      "provided_value": "invalid_id"
    },
    "request_id": "req_123456",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `AUTHENTICATION_ERROR` | 401 | Invalid or missing authentication |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `EXTERNAL_SERVICE_ERROR` | 502 | External service unavailable |
| `INTERNAL_ERROR` | 500 | Internal server error |

## Rate Limiting

### Rate Limit Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995260
X-RateLimit-Retry-After: 60
```

### Rate Limit Response
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 100,
      "remaining": 0,
      "reset_time": "2024-01-15T10:31:00Z",
      "retry_after_seconds": 60
    }
  }
}
```

## SDK Examples

### Python SDK Usage
```python
from whatsapp_llm_client import WhatsAppLLMClient

# Initialize client
client = WhatsAppLLMClient(
    api_key="your_api_key",
    base_url="https://api.yourdomain.com/v1"
)

# Send a message
response = await client.send_message(
    chat_id="573107601252@c.us",
    content="Hello from the API!",
    priority=3
)

print(f"Message queued: {response.message_id}")

# Get conversation history
messages = await client.get_conversation_messages(
    conversation_id="conv_123456",
    limit=50
)

for message in messages:
    print(f"{message.sender_type}: {message.content}")

# Get analytics
analytics = await client.get_analytics(
    start_date="2024-01-01",
    end_date="2024-01-31"
)

print(f"Total conversations: {analytics.total_conversations}")
```

### JavaScript SDK Usage
```javascript
import { WhatsAppLLMClient } from 'whatsapp-llm-sdk';

const client = new WhatsAppLLMClient({
  apiKey: 'your_api_key',
  baseURL: 'https://api.yourdomain.com/v1'
});

// Send message
const response = await client.sendMessage({
  chatId: '573107601252@c.us',
  content: 'Hello from JavaScript!',
  priority: 3
});

console.log(`Message ID: ${response.messageId}`);

// Stream conversation updates
const stream = client.streamConversation('conv_123456');

for await (const update of stream) {
  console.log('New message:', update.message);
}
```

### cURL Examples

#### Send Message
```bash
curl -X POST "https://api.yourdomain.com/v1/messages" \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "573107601252@c.us",
    "content": "Hello, World!",
    "priority": 3
  }'
```

#### Get Conversation
```bash
curl -H "Authorization: Bearer your_api_token" \
     "https://api.yourdomain.com/v1/conversations/conv_123456"
```

#### List Conversations with Filtering
```bash
curl -H "Authorization: Bearer your_api_token" \
     "https://api.yourdomain.com/v1/conversations?limit=10&start_date=2024-01-01T00:00:00Z"
```

## Webhook Security

### Webhook Signature Verification
```python
import hmac
import hashlib
import os

def verify_whatsapp_signature(payload: bytes, signature: str) -> bool:
    """Verify WhatsApp webhook signature."""
    secret = os.getenv('WHATSAPP_WEBHOOK_SECRET')

    # Remove 'sha256=' prefix
    signature_hash = signature.replace('sha256=', '')

    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison
    return hmac.compare_digest(signature_hash, expected_signature)

# Usage in webhook handler
@app.post("/v1/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    signature: str = Header(None, alias="X-Hub-Signature-256")
):
    payload = await request.body()

    if not verify_whatsapp_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process webhook payload
    data = await request.json()
    await process_whatsapp_message(data)

    return {"status": "processed"}
```

## API Versioning

### Version Strategy
- **URL Path Versioning**: `/v1/resource`
- **Header Versioning**: `Accept: application/vnd.whatsapp-llm.v1+json`
- **Semantic Versioning**: Major.Minor.Patch (1.0.0)

### Breaking Changes Policy
- **Major Version**: Breaking changes (2.0.0)
- **Minor Version**: New features, backward compatible (1.1.0)
- **Patch Version**: Bug fixes, no API changes (1.0.1)

### Deprecation Headers
```http
X-API-Deprecated: true
X-API-Deprecation-Date: 2024-06-01
X-API-Sunset-Date: 2024-12-01
X-API-Successor-Version: v2
```

## Pagination

### Cursor-Based Pagination
```json
{
  "data": [...],
  "pagination": {
    "has_more": true,
    "next_cursor": "eyJpZCI6Im1zZ18xMjMiLCJ0aW1lc3RhbXAiOiIyMDI0LTAxLTE1VDEwOjMwOjAwWiJ9",
    "prev_cursor": null,
    "total_count": 1250
  }
}
```

### Offset-Based Pagination
```json
{
  "data": [...],
  "pagination": {
    "total": 1250,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

## File Upload

### Upload Document
```http
POST /v1/files/upload
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: The file to upload
- `conversation_id`: Associated conversation ID
- `metadata`: JSON string with file metadata

**Response:**
```json
{
  "file_id": "file_123456",
  "filename": "document.pdf",
  "size_bytes": 2048576,
  "mime_type": "application/pdf",
  "url": "https://files.yourdomain.com/file_123456.pdf",
  "uploaded_at": "2024-01-15T10:30:00Z"
}
```

### Supported File Types
- **Documents**: PDF, DOC, DOCX, TXT (max 10MB)
- **Images**: JPG, PNG, GIF (max 5MB)
- **Audio**: MP3, WAV, M4A (max 25MB)
- **Video**: MP4, AVI (max 100MB)

This comprehensive API reference provides everything needed to integrate with the WhatsApp LLM Chatbot platform, including detailed endpoint documentation, authentication, error handling, and practical examples.