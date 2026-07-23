"""Offline source adapters: raw records -> AURORA import packages.

Adapters never call the network and never invent evidence. They only reshape
caller-supplied JSON into the contract in ``docs/import-schema.md``.
"""

from .filings import convert_filings
from .jobs import convert_jobs
from .news import convert_news
from .openalex import convert_openalex
from .package_util import merge_packages, strip_package
from .patentsview import convert_patentsview
from .uspto import convert_uspto

__all__ = [
    "convert_uspto",
    "convert_patentsview",
    "convert_jobs",
    "convert_news",
    "convert_openalex",
    "convert_filings",
    "merge_packages",
    "strip_package",
]
__version__ = "0.1.5"
