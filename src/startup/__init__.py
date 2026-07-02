"""startup/__init__.py"""

# from .??? import ???

from pathlib import Path

def add_to_startup(configs_dir: str|Path, python_executable: str):
    raise NotImplementedError()

def remove_from_startup(configs_dir: str|Path):
    raise NotImplementedError()

def is_in_startup(configs_dir: str|Path) -> bool:
    raise NotImplementedError()

__all__ = ["is_in_startup", "add_to_startup", "remove_from_startup"]
