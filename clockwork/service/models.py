"""Pydantic models for Clockwork service API."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from clockwork.resources.base import Resource


class ProjectState(BaseModel):
    """State representation for a monitored project.

    Attributes:
        project_id: Unique project identifier (UUID string)
        main_file: Path to the project's main.py file
        resources: List of resource definitions from the project
        last_check: Dictionary mapping resource names to last check timestamps
        health_status: Dictionary mapping resource names to health status (True=healthy)
        remediation_attempts: Dictionary tracking remediation attempt counts per resource
        registered_at: Timestamp when project was registered
    """

    project_id: str = Field(..., description="Unique project identifier (UUID)")
    main_file: Path = Field(..., description="Path to main.py")
    resources: List[Resource] = Field(default_factory=list, description="Project resources")
    last_check: Dict[str, datetime] = Field(
        default_factory=dict,
        description="Resource name -> last check timestamp"
    )
    health_status: Dict[str, bool] = Field(
        default_factory=dict,
        description="Resource name -> health status (True=healthy, False=unhealthy)"
    )
    remediation_attempts: Dict[str, int] = Field(
        default_factory=dict,
        description="Resource name -> remediation attempt count"
    )
    registered_at: datetime = Field(
        default_factory=datetime.now,
        description="Registration timestamp"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True  # Allow Resource types


class ProjectRegistrationRequest(BaseModel):
    """API request model for registering a project.

    Attributes:
        main_file: Path to the project's main.py file (as string)
    """

    main_file: str = Field(..., description="Path to main.py file")


class ProjectStatusResponse(BaseModel):
    """API response model for project status.

    Attributes:
        project_id: Unique project identifier
        resource_count: Total number of resources in project
        healthy_count: Number of healthy resources
        unhealthy_count: Number of unhealthy resources
        last_check: Timestamp of last health check (if any)
    """

    project_id: str = Field(..., description="Unique project identifier")
    resource_count: int = Field(..., description="Total resource count")
    healthy_count: int = Field(..., description="Healthy resource count")
    unhealthy_count: int = Field(..., description="Unhealthy resource count")
    last_check: Optional[datetime] = Field(None, description="Last check timestamp")


class RemediationRequest(BaseModel):
    """API request model for triggering remediation.

    Attributes:
        resource_name: Optional specific resource to remediate (if None, all unhealthy)
    """

    resource_name: Optional[str] = Field(None, description="Specific resource to remediate")
