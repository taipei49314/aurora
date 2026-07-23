"""AURORA — Unknown Industry Discovery Engine.

Local-first, deterministic, evidence-grounded. No external API or LLM at runtime.
"""
from .config import DEFAULT_CONFIG, EngineConfig
from .importing import import_package
from .taxonomy import Taxonomy
from .pipeline import run_pipeline

__all__ = ["DEFAULT_CONFIG", "EngineConfig", "import_package", "Taxonomy", "run_pipeline"]
__version__ = "0.1.26"
