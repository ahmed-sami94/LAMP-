import sys
from common import rpc

try:
    result = rpc("health")
    sys.exit(0 if all(result["services"].values()) else 1)
except Exception:
    sys.exit(1)
