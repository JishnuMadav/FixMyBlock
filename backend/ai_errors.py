"""Public errors never expose provider payloads, credentials, or internal configuration."""
from fastapi import HTTPException


def assistant_error(exc):
    code = getattr(exc, 'code', None)
    if str(code) == '429':
        return HTTPException(429,
            'The AI service has reached its usage limit. No report was submitted. '
            'Please wait before retrying; a daily limit may require the demo administrator to restore quota.',
            headers={'Retry-After': '60'})
    return HTTPException(503,
        'The AI service is temporarily unavailable. No report was submitted. Your last message was not processed; please retry shortly.')
