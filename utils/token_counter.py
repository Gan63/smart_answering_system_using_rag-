from typing import Dict, Any, Optional
from openai import OpenAI

def count_tokens_from_response(response: Any) -> Dict[str, int]:
    '''
    Extract token usage from OpenAI/OpenRouter response.
    Returns {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int}
    '''
    try:
        usage = response.choices[0].usage
        return {
            'prompt_tokens': getattr(usage, 'prompt_tokens', 0),
            'completion_tokens': getattr(usage, 'completion_tokens', 0),
            'total_tokens': getattr(usage, 'total_tokens', 0)
        }
    except (AttributeError, IndexError, TypeError):
        print('[WARN] No usage info in response, using fallback.')
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

def estimate_tokens(text: str) -> int:
    '''
    Rough fallback: ~4 chars per token.
    '''
    return len(text) // 4 + 1
