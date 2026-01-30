import yaml
import os
from typing import Dict, Any

def load_config(path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        config = yaml.safe_load(f)
    
    return config

def get_env_var(name: str, default: str = None) -> str:
    """Get environment variable or raise error."""
    value = os.environ.get(name, default)
    if value is None:
        raise ValueError(f"Environment variable {name} not set")
    return value
