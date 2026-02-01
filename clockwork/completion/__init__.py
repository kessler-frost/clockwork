"""
Completion module - AI completion caching and utilities.

Provides caching infrastructure for reproducible AI completions.
"""

from .cache import CacheError, CompletionCache

__all__ = ["CacheError", "CompletionCache"]
