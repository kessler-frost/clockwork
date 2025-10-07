"""Clockwork assertions module for validating resource runtime state.

This module provides type-safe assertions that compile to PyInfra operations
for validating that deployed resources match their desired state.

Assertion Categories:
    - HTTP: Web service health checks, port accessibility, response times
    - Container: Docker container status, health, and logs
    - File: File existence, permissions, size, content validation
    - Resource: Memory, CPU, and disk usage monitoring
    - Process: Process running/not running validation

Example:
    >>> from clockwork.assertions import (
    ...     HealthcheckAssert,
    ...     ContainerRunningAssert,
    ...     FileExistsAssert,
    ...     MemoryUsageAssert,
    ...     ProcessRunningAssert,
    ... )
    >>> from clockwork.resources import DockerServiceResource
    >>>
    >>> # Docker service with assertions
    >>> nginx = DockerServiceResource(
    ...     name="nginx",
    ...     description="Web server",
    ...     ports=["80:80"],
    ...     assertions=[
    ...         ContainerRunningAssert(),
    ...         HealthcheckAssert(url="http://localhost:80", expected_status=200),
    ...         MemoryUsageAssert(max_mb=512, container_name="nginx"),
    ...     ]
    ... )
"""

# Base assertion class
from .base import BaseAssertion

# HTTP assertions
from .http import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ResponseTimeAssert,
)

# Container assertions
from .container import (
    ContainerRunningAssert,
    ContainerHealthyAssert,
    LogContainsAssert,
)

# File assertions
from .file import (
    FileExistsAssert,
    FilePermissionsAssert,
    FileSizeAssert,
    FileContentMatchesAssert,
)

# Resource usage assertions
from .resource import (
    MemoryUsageAssert,
    CpuUsageAssert,
    DiskUsageAssert,
)

# Process assertions
from .process import (
    ProcessRunningAssert,
    ProcessNotRunningAssert,
)

__all__ = [
    # Base
    "BaseAssertion",
    # HTTP
    "HealthcheckAssert",
    "PortAccessibleAssert",
    "ResponseTimeAssert",
    # Container
    "ContainerRunningAssert",
    "ContainerHealthyAssert",
    "LogContainsAssert",
    # File
    "FileExistsAssert",
    "FilePermissionsAssert",
    "FileSizeAssert",
    "FileContentMatchesAssert",
    # Resource
    "MemoryUsageAssert",
    "CpuUsageAssert",
    "DiskUsageAssert",
    # Process
    "ProcessRunningAssert",
    "ProcessNotRunningAssert",
]
