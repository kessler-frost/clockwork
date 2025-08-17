"""
Planner module for converting intermediate representation (IR) to ActionList.

This module provides functionality to take validated IR and generate an ordered
ActionList with deterministic steps for task execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
import logging


logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Enumeration of supported action types in the clockwork system."""
    
    FETCH_REPO = "fetch_repo"
    BUILD_IMAGE = "build_image"
    ENSURE_SERVICE = "ensure_service" 
    VERIFY_HTTP = "verify_http"
    CREATE_NAMESPACE = "create_namespace"
    APPLY_CONFIG = "apply_config"
    WAIT_FOR_READY = "wait_for_ready"
    CLEANUP = "cleanup"


@dataclass
class Action:
    """
    Represents a single action in the execution pipeline.
    
    Attributes:
        action_type: The type of action to perform
        name: Unique identifier for this action
        parameters: Parameters required for the action
        dependencies: List of action names this action depends on
        retry_count: Number of times to retry on failure
        timeout_seconds: Timeout for the action in seconds
    """
    
    action_type: ActionType
    name: str
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 3
    timeout_seconds: int = 300
    
    def __post_init__(self):
        """Validate action parameters after initialization."""
        if not self.name:
            raise ValueError("Action name cannot be empty")
        
        if not isinstance(self.parameters, dict):
            raise ValueError("Action parameters must be a dictionary")
        
        # Validate dependencies are strings
        if not all(isinstance(dep, str) for dep in self.dependencies):
            raise ValueError("All dependencies must be strings")


@dataclass
class ActionList:
    """
    Represents an ordered list of actions to execute.
    
    Attributes:
        actions: List of actions to execute
        metadata: Additional metadata about the action list
    """
    
    actions: List[Action]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate the action list after initialization."""
        if not isinstance(self.actions, list):
            raise ValueError("Actions must be a list")
        
        # Validate all items are Action instances
        for i, action in enumerate(self.actions):
            if not isinstance(action, Action):
                raise ValueError(f"Item at index {i} is not an Action instance")
    
    def get_action_names(self) -> Set[str]:
        """Get set of all action names in this list."""
        return {action.name for action in self.actions}
    
    def validate_dependencies(self) -> bool:
        """
        Validate that all dependencies reference existing actions.
        
        Returns:
            True if all dependencies are valid, False otherwise
        """
        action_names = self.get_action_names()
        
        for action in self.actions:
            for dep in action.dependencies:
                if dep not in action_names:
                    logger.error(f"Action '{action.name}' depends on non-existent action '{dep}'")
                    return False
        
        return True


class PlannerError(Exception):
    """Base exception for planner-related errors."""
    pass


class InvalidIRError(PlannerError):
    """Raised when the input IR is invalid or malformed."""
    pass


class DependencyError(PlannerError):
    """Raised when there are dependency resolution issues."""
    pass


def convert_ir_to_actions(ir_data: Dict[str, Any]) -> ActionList:
    """
    Convert intermediate representation to an ordered ActionList.
    
    This function takes validated IR and generates a deterministic sequence
    of actions required to achieve the desired state.
    
    Args:
        ir_data: Dictionary containing the intermediate representation
        
    Returns:
        ActionList: Ordered list of actions to execute
        
    Raises:
        InvalidIRError: If the IR data is invalid or malformed
        DependencyError: If dependency resolution fails
    """
    try:
        if not isinstance(ir_data, dict):
            raise InvalidIRError("IR data must be a dictionary")
        
        logger.info("Converting IR to actions")
        actions = []
        
        # Extract basic configuration
        config = ir_data.get("config", {})
        services = ir_data.get("services", {})
        repositories = ir_data.get("repositories", {})
        
        # Step 1: Create namespace if specified
        if config.get("namespace"):
            actions.append(Action(
                action_type=ActionType.CREATE_NAMESPACE,
                name="create_namespace",
                parameters={"namespace": config["namespace"]},
                dependencies=[],
                retry_count=1,
                timeout_seconds=60
            ))
        
        # Step 2: Fetch repositories
        repo_actions = []
        for repo_name, repo_config in repositories.items():
            action_name = f"fetch_repo_{repo_name}"
            repo_actions.append(action_name)
            
            actions.append(Action(
                action_type=ActionType.FETCH_REPO,
                name=action_name,
                parameters={
                    "repository_url": repo_config.get("url"),
                    "branch": repo_config.get("branch", "main"),
                    "destination": repo_config.get("destination", f"./{repo_name}")
                },
                dependencies=[]
            ))
        
        # Step 3: Build images
        image_actions = []
        for service_name, service_config in services.items():
            if service_config.get("build"):
                action_name = f"build_image_{service_name}"
                image_actions.append(action_name)
                
                # Determine dependencies - usually depends on repo fetch
                deps = []
                if service_config.get("source_repo"):
                    deps.append(f"fetch_repo_{service_config['source_repo']}")
                
                actions.append(Action(
                    action_type=ActionType.BUILD_IMAGE,
                    name=action_name,
                    parameters={
                        "dockerfile": service_config["build"].get("dockerfile", "Dockerfile"),
                        "context": service_config["build"].get("context", "."),
                        "tag": service_config.get("image", f"{service_name}:latest"),
                        "build_args": service_config["build"].get("args", {})
                    },
                    dependencies=deps
                ))
        
        # Step 4: Ensure services are running
        service_actions = []
        for service_name, service_config in services.items():
            action_name = f"ensure_service_{service_name}"
            service_actions.append(action_name)
            
            # Dependencies: namespace creation and image building (if applicable)
            deps = []
            if config.get("namespace"):
                deps.append("create_namespace")
            if f"build_image_{service_name}" in [a.name for a in actions]:
                deps.append(f"build_image_{service_name}")
            
            actions.append(Action(
                action_type=ActionType.ENSURE_SERVICE,
                name=action_name,
                parameters={
                    "service_name": service_name,
                    "image": service_config.get("image"),
                    "ports": service_config.get("ports", []),
                    "environment": service_config.get("environment", {}),
                    "replicas": service_config.get("replicas", 1),
                    "namespace": config.get("namespace", "default")
                },
                dependencies=deps
            ))
        
        # Step 5: Wait for services to be ready
        wait_actions = []
        for service_name in services.keys():
            action_name = f"wait_ready_{service_name}"
            wait_actions.append(action_name)
            
            actions.append(Action(
                action_type=ActionType.WAIT_FOR_READY,
                name=action_name,
                parameters={
                    "service_name": service_name,
                    "namespace": config.get("namespace", "default"),
                    "timeout_seconds": 300
                },
                dependencies=[f"ensure_service_{service_name}"]
            ))
        
        # Step 6: Verify HTTP endpoints
        for service_name, service_config in services.items():
            if service_config.get("health_check"):
                health_config = service_config["health_check"]
                action_name = f"verify_http_{service_name}"
                
                actions.append(Action(
                    action_type=ActionType.VERIFY_HTTP,
                    name=action_name,
                    parameters={
                        "service_name": service_name,
                        "endpoint": health_config.get("path", "/health"),
                        "expected_status": health_config.get("status_code", 200),
                        "timeout_seconds": health_config.get("timeout", 30),
                        "namespace": config.get("namespace", "default")
                    },
                    dependencies=[f"wait_ready_{service_name}"]
                ))
        
        action_list = ActionList(
            actions=actions,
            metadata={
                "generated_from": "ir_conversion",
                "total_actions": len(actions),
                "timestamp": "placeholder_for_actual_timestamp"
            }
        )
        
        # Validate the generated action list
        if not action_list.validate_dependencies():
            raise DependencyError("Generated action list has invalid dependencies")
        
        logger.info(f"Successfully converted IR to {len(actions)} actions")
        return action_list
        
    except Exception as e:
        logger.error(f"Failed to convert IR to actions: {str(e)}")
        if isinstance(e, (InvalidIRError, DependencyError)):
            raise
        raise InvalidIRError(f"Unexpected error during IR conversion: {str(e)}")


def validate_action_list(action_list: ActionList) -> bool:
    """
    Validate that an ActionList is well-formed and executable.
    
    Args:
        action_list: The ActionList to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        if not isinstance(action_list, ActionList):
            logger.error("Input is not an ActionList instance")
            return False
        
        # Check that all actions are valid
        for action in action_list.actions:
            if not isinstance(action, Action):
                logger.error(f"Invalid action found: {action}")
                return False
        
        # Check for duplicate action names
        action_names = [action.name for action in action_list.actions]
        if len(action_names) != len(set(action_names)):
            logger.error("Duplicate action names found")
            return False
        
        # Validate dependencies
        if not action_list.validate_dependencies():
            return False
        
        # Check for circular dependencies
        if _has_circular_dependencies(action_list):
            logger.error("Circular dependencies detected")
            return False
        
        logger.info("ActionList validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Error during ActionList validation: {str(e)}")
        return False


def optimize_action_list(action_list: ActionList) -> ActionList:
    """
    Optimize an ActionList for better performance and resource utilization.
    
    This function analyzes the action list and applies optimizations such as:
    - Parallelizing independent actions
    - Removing redundant actions
    - Reordering for better efficiency
    
    Args:
        action_list: The ActionList to optimize
        
    Returns:
        ActionList: Optimized version of the input list
    """
    try:
        if not validate_action_list(action_list):
            logger.warning("Cannot optimize invalid ActionList")
            return action_list
        
        # Create a copy to avoid modifying the original
        optimized_actions = action_list.actions.copy()
        
        # TODO: Implement actual optimization algorithms
        # For now, just return the original list with updated metadata
        
        optimized_metadata = action_list.metadata.copy()
        optimized_metadata.update({
            "optimized": True,
            "optimization_applied": "basic_validation_only"
        })
        
        return ActionList(
            actions=optimized_actions,
            metadata=optimized_metadata
        )
        
    except Exception as e:
        logger.error(f"Error during ActionList optimization: {str(e)}")
        return action_list


def _has_circular_dependencies(action_list: ActionList) -> bool:
    """
    Check if the ActionList has circular dependencies using DFS.
    
    Args:
        action_list: The ActionList to check
        
    Returns:
        bool: True if circular dependencies exist, False otherwise
    """
    # Build adjacency list
    graph = {}
    for action in action_list.actions:
        graph[action.name] = action.dependencies
    
    # Track visit states: 0=unvisited, 1=visiting, 2=visited
    visit_state = {name: 0 for name in graph.keys()}
    
    def dfs(node: str) -> bool:
        if visit_state[node] == 1:  # Currently visiting - cycle detected
            return True
        if visit_state[node] == 2:  # Already visited
            return False
        
        visit_state[node] = 1  # Mark as visiting
        
        for neighbor in graph.get(node, []):
            if neighbor in visit_state and dfs(neighbor):
                return True
        
        visit_state[node] = 2  # Mark as visited
        return False
    
    # Check all nodes
    for node in graph.keys():
        if visit_state[node] == 0 and dfs(node):
            return True
    
    return False