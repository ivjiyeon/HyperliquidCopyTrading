from typing import Dict, Any
import yaml

def load_config() -> Dict[str, Any]:
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("config.yaml not found! Create it using the example above.")
        exit(1)
    except Exception as e:
        print(f"Error reading config.yaml: {e}")
        exit(1)