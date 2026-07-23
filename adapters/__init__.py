"""Offline source adapters: raw records -> AURORA import packages.

Adapters never call the network and never invent evidence. They only reshape
caller-supplied JSON into the contract in ``docs/import-schema.md``.
"""

from .jobs import convert_jobs
from .news import convert_news
from .package_util import merge_packages, strip_package
from .patentsview import convert_patentsview
from .uspto import convert_uspto

__all__ = [
    "convert_uspto",
    "convert_patentsview",
    "convert_jobs",
    "convert_news",
    "merge_packages",
    "strip_package",
]
__version__ = "0.1.0"
