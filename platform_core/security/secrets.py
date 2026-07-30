import os
from dotenv import load_dotenv
from platform_core.logging_config import get_logger

load_dotenv(override=True)

logger = get_logger(__name__)

def get_secret(key: str, default: str = None) -> str:
    """
    Retrieves a secret by key.
    
    For Phase Group 2, this loads from environment variables (.env).
    In the future, this will swap to a real vault (e.g., AWS Secrets Manager, HashiCorp Vault)
    without requiring any changes to the rest of the codebase.
    
    Args:
        key: The name of the secret (e.g., 'POSTGRES_USER')
        default: Optional fallback value. If not provided and the secret is missing, it raises an error.
        
    Raises:
        ValueError: If the secret is missing and no default is provided.
    """
    value = os.getenv(key, default)
    
    if value is None:
        logger.critical(
            f"Missing required secret: {key}",
            extra={"secret_key": key, "catch_reason": "Fail-fast on missing configuration"}
        )
        raise ValueError(f"Secret '{key}' is required but not found in the environment.")
        
    return value
