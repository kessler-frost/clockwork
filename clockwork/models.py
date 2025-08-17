"""
Centralized Pydantic models for Clockwork task orchestration platform.

This module contains the core data models used throughout the Clockwork pipeline:
- IR (Intermediate Representation) from intake
- ActionList from assembly  
- ArtifactBundle from forge
- State management models for task execution
"""

from typing import Dict, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import json


# =============================================================================
# Core Enums
# =============================================================================

class ActionType(str, Enum):
    """Supported action types in Clockwork."""
    FETCH_REPO = "fetch_repo"
    BUILD_IMAGE = "build_image"
    ENSURE_SERVICE = "ensure_service"
    VERIFY_HTTP = "verify_http"
    EXECUTE_SCRIPT = "execute_script"
    COPY_FILES = "copy_files"
    SET_ENVIRONMENT = "set_environment"


class ResourceType(str, Enum):
    """Supported resource types."""
    SERVICE = "service"
    IMAGE = "image"
    NETWORK = "network"
    VOLUME = "volume"
    SECRET = "secret"
    CONFIG = "config"


class ExecutionStatus(str, Enum):
    """Execution status for actions and resources."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# Intermediate Representation (IR) Models
# =============================================================================

class Variable(BaseModel):
    """Variable definition in .cw files."""
    name: str
    type: str = "string"
    default: Optional[Any] = None
    description: Optional[str] = None
    required: bool = True


class Provider(BaseModel):
    """Provider configuration."""
    name: str
    source: str
    version: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    """Resource definition in .cw files."""
    type: ResourceType
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    tags: Dict[str, str] = Field(default_factory=dict)


class Module(BaseModel):
    """Module definition for reusable components."""
    name: str
    source: str
    version: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)


class Output(BaseModel):
    """Output definition."""
    name: str
    value: Any
    description: Optional[str] = None
    sensitive: bool = False


class IR(BaseModel):
    """Intermediate Representation - parsed and validated .cw configuration."""
    version: str = "1.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    variables: Dict[str, Variable] = Field(default_factory=dict)
    providers: List[Provider] = Field(default_factory=list)
    resources: Dict[str, Resource] = Field(default_factory=dict)
    modules: Dict[str, Module] = Field(default_factory=dict)
    outputs: Dict[str, Output] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @validator('version')
    def validate_version(cls, v):
        """Validate version format."""
        if not v or not isinstance(v, str):
            raise ValueError("Version must be a non-empty string")
        return v


# =============================================================================
# Assembly Models (ActionList)
# =============================================================================

class Action(BaseModel):
    """Individual action in the execution plan."""
    name: str
    type: ActionType
    args: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    timeout: int = 300  # seconds
    retries: int = 3
    retry_delay: int = 5  # seconds
    condition: Optional[str] = None  # condition for execution
    
    @validator('timeout')
    def validate_timeout(cls, v):
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v

    @validator('retries')
    def validate_retries(cls, v):
        """Validate retries is non-negative."""
        if v < 0:
            raise ValueError("Retries must be non-negative")
        return v


class ActionList(BaseModel):
    """Ordered list of actions from assembly phase."""
    version: str = "1"
    steps: List[Action] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    def to_json(self) -> str:
        """Convert to JSON string for serialization."""
        return json.dumps(self.dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> 'ActionList':
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


# =============================================================================
# Forge Models (ArtifactBundle)
# =============================================================================

class Artifact(BaseModel):
    """Individual artifact (script/file) in the bundle."""
    path: str
    mode: str = "0644"  # file permissions
    purpose: str  # which action this artifact serves
    lang: str  # programming language
    content: str
    checksum: Optional[str] = None

    @validator('mode')
    def validate_mode(cls, v):
        """Validate file mode format."""
        if not v.startswith('0') or len(v) != 4:
            raise ValueError("Mode must be in format '0644'")
        return v


class ExecutionStep(BaseModel):
    """Execution step for artifacts."""
    purpose: str
    run: Dict[str, Any]  # command configuration
    env: Dict[str, str] = Field(default_factory=dict)
    working_dir: Optional[str] = None


class ArtifactBundle(BaseModel):
    """Complete bundle of artifacts from compiler agent."""
    version: str = "1"
    artifacts: List[Artifact] = Field(default_factory=list)
    steps: List[ExecutionStep] = Field(default_factory=list)
    vars: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    def to_json(self) -> str:
        """Convert to JSON string for serialization."""
        return json.dumps(self.dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> 'ArtifactBundle':
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


# =============================================================================
# State Management Models
# =============================================================================

class ResourceState(BaseModel):
    """State of an individual resource."""
    resource_id: str
    type: ResourceType
    status: ExecutionStatus
    config: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    last_applied: Optional[datetime] = None
    last_verified: Optional[datetime] = None
    drift_detected: bool = False
    error_message: Optional[str] = None


class ExecutionRecord(BaseModel):
    """Record of an execution run."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: ExecutionStatus
    action_list_checksum: str
    artifact_bundle_checksum: str
    resource_states: List[ResourceState] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class ClockworkState(BaseModel):
    """Complete state of the Clockwork system."""
    version: str = "1.0"
    last_applied_ir: Optional[IR] = None
    current_resources: Dict[str, ResourceState] = Field(default_factory=dict)
    execution_history: List[ExecutionRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def update_timestamp(self):
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()


# =============================================================================
# Environment and Configuration Models
# =============================================================================

class Environment(BaseModel):
    """Environment configuration and facts."""
    name: str = "default"
    variables: Dict[str, str] = Field(default_factory=dict)
    facts: Dict[str, Any] = Field(default_factory=dict)  # discovered environment info
    constraints: Dict[str, Any] = Field(default_factory=dict)  # resource limits, etc.


class ClockworkConfig(BaseModel):
    """Global Clockwork configuration."""
    project_name: str
    version: str = "1.0"
    default_timeout: int = 300
    max_retries: int = 3
    state_file: str = ".clockwork/state.json"
    build_dir: str = ".clockwork/build"
    log_level: str = "INFO"
    agent_config: Dict[str, Any] = Field(default_factory=dict)
    environment: Environment = Field(default_factory=Environment)


# =============================================================================
# Validation Results and Errors
# =============================================================================

class ValidationIssue(BaseModel):
    """Individual validation issue."""
    level: Literal["error", "warning", "info"]
    message: str
    field_path: Optional[str] = None
    line_number: Optional[int] = None


class ValidationResult(BaseModel):
    """Result of validation operations."""
    valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    
    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [issue for issue in self.issues if issue.level == "error"]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [issue for issue in self.issues if issue.level == "warning"]


# =============================================================================
# Export all models
# =============================================================================

__all__ = [
    # Enums
    'ActionType', 'ResourceType', 'ExecutionStatus',
    
    # IR Models
    'Variable', 'Provider', 'Resource', 'Module', 'Output', 'IR',
    
    # Assembly Models  
    'Action', 'ActionList',
    
    # Forge Models
    'Artifact', 'ExecutionStep', 'ArtifactBundle',
    
    # State Models
    'ResourceState', 'ExecutionRecord', 'ClockworkState',
    
    # Config Models
    'Environment', 'ClockworkConfig',
    
    # Validation Models
    'ValidationIssue', 'ValidationResult',
]