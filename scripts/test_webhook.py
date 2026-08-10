import asyncio
import httpx
import json

async def test_webhook():
    print("Testing Datadog Webhook Payload...")
    datadog_payload = {
        "event_type": "monitor_alert",
        "monitor": {
            "name": "High Error Rate on customer_profile_ingestion",
            "type": "query alert"
        },
        "event_title": "[Triggered] High Error Rate",
        "event_msg": "The error rate for customer_profile_ingestion is above 5% for the last 10 minutes.",
        "tags": "env:prod, service:customer_profile"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post("http://127.0.0.1:8000/api/v1/ingest/webhook", json=datadog_payload)
            print(f"Response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error: {e}")

    print("\nTesting Email-to-Webhook Payload...")
    email_payload = {
        "headers": {
            "From": "noreply@snowflake.com",
            "Subject": "Task Failure Notification: LOAD_CUSTOMER_DATA"
        },
        "text": "Task LOAD_CUSTOMER_DATA failed at 2026-08-06 09:30 UTC. Error: Division by zero."
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post("http://127.0.0.1:8000/api/v1/ingest/webhook", json=email_payload)
            print(f"Response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error: {e}")
            
    print("\nTesting Noise/Spam Payload...")
    spam_payload = {
        "headers": {
            "From": "marketing@newsletter.com",
            "Subject": "Try our new features!"
        },
        "text": "We just launched our new dashboard UI."
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post("http://127.0.0.1:8000/api/v1/ingest/webhook", json=spam_payload)
            print(f"Response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook())
