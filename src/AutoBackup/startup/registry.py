import json
from pathlib import Path

from .logger import logger
from .ensure import ensure_startup_entry, remove_startup_entry

STARTUP_REGISTRY = Path.home() / "AutoBackup" / "startup.json"

def _normalize_key(configs_dir: str|Path) -> str:
    return str(Path(configs_dir).resolve())

def load_registry() -> dict:
    registry = {}
    try:
        with open(STARTUP_REGISTRY, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"Failed to load startup registry: {e}")
        raise
    logger.debug("Loaded startup registry")
    return registry

def save_registry(registry: dict):
    try:
        STARTUP_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        with open(STARTUP_REGISTRY, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=4)
        if registry:
            ensure_startup_entry()
        else:
            remove_startup_entry()
    except Exception as e:
        logger.error(f"Failed to save startup registry: {e}")
        raise
    logger.debug("Saved startup registry")

def add_to_startup(configs_dir: str|Path, python_executable: str):
    configs_dir = _normalize_key(configs_dir)
    registry = load_registry()
    registry[configs_dir] = str(python_executable)
    save_registry(registry)
    logger.info(f"Added {configs_dir} to startup")

def remove_from_startup(configs_dir: str|Path):
    configs_dir = _normalize_key(configs_dir)
    registry = load_registry()
    registry.pop(configs_dir, None)
    save_registry(registry)
    logger.info(f"Removed {configs_dir} from startup")

def is_in_startup(configs_dir: str|Path) -> bool:
    return _normalize_key(configs_dir) in load_registry()
