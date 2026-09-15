import json
import os
from urllib.request import Request, urlopen


def explain_result(question, result):
    """Optionally improve a safe, already-computed answer with an LLM explanation."""
    api_key = os.getenv('LLM_API_KEY', '').strip()
    base_url = os.getenv('LLM_BASE_URL', '').strip()
    if not api_key or not base_url or result.get('intent') in {'blocked', 'empty'}:
        return None

    endpoint = base_url.rstrip('/')
    if not endpoint.endswith('/chat/completions'):
        endpoint += '/chat/completions'
    payload = {
        'model': os.getenv('LLM_MODEL', 'gpt-4o-mini'),
        'temperature': 0,
        'messages': [
            {'role': 'system', 'content': 'Explain the supplied read-only finance result. Do not invent facts or suggest database changes.'},
            {'role': 'user', 'content': json.dumps({'question': question, 'result': result}, default=str)},
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode('utf-8'))
        return body['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, OSError, TypeError, ValueError):
        return None
