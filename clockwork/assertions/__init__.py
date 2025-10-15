"""Clockwork assertions module for validating resource runtime state.

This module provides type-safe assertions for validating that deployed
resources match their desired state.

Assertion Categories:
    - HTTP: Web service health checks, port accessibility
    - Container: Container status
    - File: File existence, content validation

Example:
    >>> from clockwork.assertions import (
    ...     HealthcheckAssert,
    ...     ContainerRunningAssert,
    ...     FileExistsAssert,
    ... )
    >>> from clockwork.resources import AppleContainerResource
    >>>
    >>> # Container service with assertions
    >>> nginx = AppleContainerResource(
    ...     name="nginx",
    ...     description="Web server",
    ...     ports=["8080:80"],
    ...     assertions=[
    ...         ContainerRunningAssert(),
    ...         HealthcheckAssert(url="http://localhost:8080", expected_status=200),
    ...     ]
    ... )
"""

# Base assertion class
from .base import BaseAssertion

# HTTP assertions
from .http import (
    HealthcheckAssert,
    PortAccessibleAssert,
)

# Container assertions
from .container import (
    ContainerRunningAssert,
)

# File assertions
from .file import (
    FileExistsAssert,
    FileContentMatchesAssert,
)

__all__ = [
    # Base
    "BaseAssertion",
    # HTTP
    "HealthcheckAssert",
    "PortAccessibleAssert",
    # Container
    "ContainerRunningAssert",
    # File
    "FileExistsAssert",
    "FileContentMatchesAssert",
]
