"""
Config Loader
Loads document type configurations from YAML files.
Adding a new document type = dropping a new YAML file in /config
No code changes required.
"""

import yaml
from pathlib import Path
from functools import lru_cache
from typing import Optional


CONFIG_DIR = Path("config")



def load_config(doc_type: str) -> dict:
    config_path = CONFIG_DIR / f"{doc_type}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No config found for document type: '{doc_type}'")
    with open(config_path) as f:
        return yaml.safe_load(f)


def list_available_doc_types() -> list[dict]:
    result = []
    for config_file in CONFIG_DIR.glob("*.yaml"):
        try:
            config = load_config(config_file.stem)
            result.append({
                "type": config_file.stem,
                "display_name": config.get("display_name", config_file.stem),
                "description": config.get("description", ""),
            })
        except Exception as e:
            print(f"Error loading {config_file.stem}: {e}")  # add this line
    return result
