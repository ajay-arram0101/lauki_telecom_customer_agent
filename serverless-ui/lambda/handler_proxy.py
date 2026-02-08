"""
Quaki Customer Support Agent - Lambda Proxy to AgentCore Runtime
================================================================
Uses boto3 bedrock-agentcore client with invoke_agent_runtime method.
This connects to your deployed AgentCore runtime with STM/LTM memory.
"""

import json
import os
import logging
import uuid
import hashlib

import boto3
from botocore.config import Config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ============================================================
# Configuration
# ============================================================

RUNTIME_ID = os.environ.get('AGENTCORE_RUNTIME_ID', 'quaki-jLdRKv6u8W')
REGION = os.environ.get('AWS_REGION', 'us-east-2')
ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID', '125975759762')

# Full ARN for the AgentCore runtime
RUNTIME_ARN = f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT_ID}:runtime/{RUNTIME_ID}"


# ============================================================
# AgentCore Invocation
# ============================================================

def invoke_agentcore(prompt: str, session_id: str, actor_id: str = None) -> dict:
    """
    Invoke AgentCore runtime using boto3 invoke_agent_runtime method.
    
    Args:
        prompt: User's question
        session_id: Session ID for memory continuity (must be 33+ chars)
        actor_id: Optional user ID for LTM
        
    Returns:
        Response dict with 'result' key
    """
    # Create boto3 client with appropriate config
    config = Config(
        read_timeout=60,
        connect_timeout=30,
        retries={"max_attempts": 2},
    )
    
    client = boto3.client(
        'bedrock-agentcore',
        region_name=REGION,
        config=config
    )
    
    # Build payload matching agent's expected format
    payload = {
        "prompt": prompt,
        "session_id": session_id,
    }
    
    if actor_id:
        payload["actor_id"] = actor_id
    
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    
    logger.info(f"Invoking AgentCore runtime: {RUNTIME_ARN}")
    logger.info(f"Session: {session_id}, Payload size: {len(payload_bytes)} bytes")
    
    try:
        # Call invoke_agent_runtime
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            qualifier='DEFAULT',
            runtimeSessionId=session_id,
            runtimeUserId=actor_id or 'web-user',
            contentType='application/json',
            accept='application/json',
            payload=payload_bytes
        )
        
        logger.info(f"Got response with keys: {list(response.keys())}")
        
        # Handle streaming response
        if 'response' in response:
            event_stream = response['response']
            all_content = []
            
            for event in event_stream:
                logger.debug(f"Event type: {type(event)}, content: {str(event)[:200]}")
                
                if isinstance(event, dict):
                    # Check for different event types
                    if 'chunk' in event:
                        chunk_data = event['chunk']
                        if isinstance(chunk_data, dict) and 'bytes' in chunk_data:
                            content = chunk_data['bytes'].decode('utf-8')
                            all_content.append(content)
                        elif isinstance(chunk_data, bytes):
                            all_content.append(chunk_data.decode('utf-8'))
                    elif 'bytes' in event:
                        all_content.append(event['bytes'].decode('utf-8'))
                elif isinstance(event, bytes):
                    all_content.append(event.decode('utf-8'))
                elif hasattr(event, 'read'):
                    all_content.append(event.read().decode('utf-8'))
            
            # Combine all chunks
            combined = ''.join(all_content)
            logger.info(f"Combined response length: {len(combined)}")
            
            # Try to parse as JSON
            try:
                result = json.loads(combined)
                return result
            except json.JSONDecodeError:
                # Return as plain text result
                return {"result": combined}
        
        # If payload is returned directly
        if 'payload' in response:
            payload_data = response['payload']
            if hasattr(payload_data, 'read'):
                content = payload_data.read().decode('utf-8')
            elif isinstance(payload_data, bytes):
                content = payload_data.decode('utf-8')
            else:
                content = str(payload_data)
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"result": content}
        
        return {"result": str(response)}
        
    except Exception as e:
        logger.error(f"AgentCore invocation failed: {e}")
        logger.exception("Full traceback:")
        raise


# ============================================================
# Response Formatter - Clean up markdown responses
# ============================================================

def format_response(text: str) -> str:
    """
    Clean up agent response for better readability in chat UI.
    Converts markdown tables to plain text, cleans up formatting.
    """
    if not text:
        return text
    
    lines = text.split('\n')
    formatted_lines = []
    in_table = False
    table_headers = []
    
    for line in lines:
        stripped = line.strip()
        
        # Detect markdown table row
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            
            # Skip separator rows (|---|---|)
            if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                continue
            
            # First row with content is headers
            if not in_table:
                table_headers = cells
                in_table = True
                formatted_lines.append('')
            else:
                # Data row - format as bullet points
                if table_headers and len(cells) >= len(table_headers):
                    for i, header in enumerate(table_headers):
                        if i < len(cells) and cells[i]:
                            formatted_lines.append(f"• {header}: {cells[i]}")
                    formatted_lines.append('')
                else:
                    formatted_lines.append(' | '.join(cells))
        else:
            in_table = False
            table_headers = []
            
            # Clean up markdown bold
            cleaned = stripped.replace('**', '')
            
            # Skip lines that are just dashes
            if cleaned.replace('-', '').replace('—', '').strip() == '':
                continue
                
            formatted_lines.append(cleaned)
    
    # Clean up multiple blank lines
    result = '\n'.join(formatted_lines)
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')
    
    return result.strip()


# ============================================================
# Lambda Handler
# ============================================================

def lambda_handler(event, context):
    """
    AWS Lambda handler - Proxy to AgentCore Runtime.
    
    Expects POST body:
    {
        "query": "user question",
        "session_id": "unique-session-id",
        "actor_id": "user-identifier"  (optional)
    }
    """
    logger.info(f"Lambda invoked")
    
    # CORS headers
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    }
    
    # Handle preflight OPTIONS request
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors_headers, 'body': ''}
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        query = body.get('query', '').strip()
        raw_session_id = body.get('session_id', '')
        actor_id = body.get('actor_id', 'web-user')
        
        # Ensure session_id is at least 33 characters (AgentCore requirement)
        if not raw_session_id or len(raw_session_id) < 33:
            if raw_session_id:
                # Create deterministic UUID from short session ID
                hash_bytes = hashlib.sha256(raw_session_id.encode()).digest()
                session_id = str(uuid.UUID(bytes=hash_bytes[:16]))
                logger.info(f"Converted session_id to UUID: {session_id}")
            else:
                session_id = str(uuid.uuid4())
        else:
            session_id = raw_session_id
        
        if not query:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'Query is required',
                    'answer': 'Please provide a question.'
                })
            }
        
        logger.info(f"Query: {query[:100]}")
        logger.info(f"Session: {session_id}")
        
        # Invoke AgentCore
        try:
            result = invoke_agentcore(query, session_id, actor_id)
            
            # Extract the answer
            answer = result.get('result', str(result))
            
            # Format for better readability
            formatted_answer = format_response(answer)
            
            response_body = {
                'answer': formatted_answer,
                'session_id': session_id,
                'actor_id': result.get('actor_id', actor_id),
                'method': 'agentcore'
            }
            
            if result.get('thread_id'):
                response_body['thread_id'] = result['thread_id']
            
            logger.info(f"Success! Response length: {len(formatted_answer)}")
            
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps(response_body, ensure_ascii=False)
            }
            
        except Exception as e:
            logger.error(f"AgentCore failed: {e}")
            
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': str(e),
                    'answer': 'Sorry, there was an error processing your request. Please try again.',
                    'session_id': session_id
                })
            }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Invalid JSON', 'answer': 'Request parsing error.'})
        }
    except Exception as e:
        logger.exception(f"Handler error: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': str(e),
                'answer': 'An unexpected error occurred. Please try again.'
            })
        }
