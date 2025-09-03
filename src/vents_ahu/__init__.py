"""Public package interface for ``vents_ahu``."""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("vents-ahu")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

# Public API (kept for backward compatibility)
from .vents import Vents

__all__ = [
    "__version__",
    "Vents",
]
