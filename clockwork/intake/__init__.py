"""
Clockwork Intake Module

This module provides functionality for parsing and validating Clockwork configuration files.
It handles the conversion of HCL (.cw) files into structured intermediate representations
and validates them according to Clockwork's schema requirements.
"""

from .parser import Parser, ParseError
from .validator import Validator, ValidationError
from .resolver import (
    Resolver, ModuleResolver, ProviderResolver, CacheManager,
    ResolutionError, ResolutionResult, resolve_references,
    VersionManager, VersionConstraint
)

__all__ = [
    "Parser",
    "ParseError", 
    "Validator",
    "ValidationError",
    "Resolver",
    "ModuleResolver",
    "ProviderResolver", 
    "CacheManager",
    "ResolutionError",
    "ResolutionResult",
    "resolve_references",
    "VersionManager",
    "VersionConstraint"
]