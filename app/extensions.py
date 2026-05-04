import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Use Redis when REDIS_URL is set (required for multi-process Render deployments so
# rate-limit state is shared across workers).  Falls back to in-process memory store
# in development/single-worker environments.
_storage_uri = os.environ.get("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=_storage_uri,
)
