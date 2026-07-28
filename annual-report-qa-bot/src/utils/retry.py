import time
from functools import wraps
from google.genai.errors import ClientError
from src.utils.logger import get_logger

logger = get_logger(__name__)

def retry_with_backoff(retries=5, initial_backoff=30):
    """
    Retries the wrapped function if a 429 Quota Exceeded error is encountered.
    Uses exponential backoff to handle Google Gemini API rate limits.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except ClientError as e:
                    if e.code == 429:
                        if attempt >= retries:
                            logger.error(f"Rate limit exhausted after {retries} retries.")
                            raise e
                        sleep_time = initial_backoff + (attempt * 10)
                        logger.warning(f"Rate limit hit in {func.__name__}. Retrying in {sleep_time} seconds (Attempt {attempt+1}/{retries})...")
                        time.sleep(sleep_time)
                        attempt += 1
                    else:
                        raise e
        return wrapper
    return decorator
