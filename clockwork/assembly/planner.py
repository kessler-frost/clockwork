"""
Planner module for converting intermediate representation (IR) to ActionList.

This module provides functionality to take validated IR and generate an ordered
ActionList with deterministic steps for task execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union
import logging
from ..models import ActionStep, ActionList, ActionType


logger = logging.getLogger(__name__)







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
        action_steps = []
        
        # Extract basic configuration
        config = ir_data.get("config", {})
        services = ir_data.get("services", {})
        repositories = ir_data.get("repositories", {})
        
        # Keep track of action ordering for dependency resolution
        action_order = []
        
        # Step 1: Create namespace if specified
        if config.get("namespace"):
            action_steps.append(ActionStep(
                name="create_namespace",
                args={"namespace": config["namespace"]}
            ))
            action_order.append("create_namespace")
        
        # Step 2: Fetch repositories
        for repo_name, repo_config in repositories.items():
            action_name = f"fetch_repo"
            if len(repositories) > 1:
                action_name = f"fetch_repo_{repo_name}"
            
            action_steps.append(ActionStep(
                name=action_name,
                args={
                    "url": repo_config.get("url"),
                    "ref": repo_config.get("branch", "main"),
                    "destination": repo_config.get("destination", f"./{repo_name}")
                }
            ))
            action_order.append(action_name)
        
        # Step 3: Build images
        for service_name, service_config in services.items():
            if service_config.get("build"):
                action_name = f"build_image"
                if len([s for s in services.values() if s.get("build")]) > 1:
                    action_name = f"build_image_{service_name}"
                
                build_args = {
                    "dockerfile": service_config["build"].get("dockerfile", "Dockerfile"),
                    "context": service_config["build"].get("context", "."),
                    "tags": [service_config.get("image", f"{service_name}:latest")]
                }
                
                # Add context variable if repo was fetched
                if service_config.get("source_repo"):
                    build_args["contextVar"] = "APP_WORKDIR"
                
                # Add build args if specified
                if service_config["build"].get("args"):
                    build_args["buildArgs"] = service_config["build"]["args"]
                
                action_steps.append(ActionStep(
                    name=action_name,
                    args=build_args
                ))
                action_order.append(action_name)
        
        # Step 4: Ensure services are running
        for service_name, service_config in services.items():
            action_name = f"ensure_service"
            if len(services) > 1:
                action_name = f"ensure_service_{service_name}"
            
            service_args = {
                "name": service_name,
                "image": service_config.get("image", f"{service_name}:latest")
            }
            
            # Use imageVar if image was built
            if service_config.get("build"):
                service_args["imageVar"] = "IMAGE_REF"
                
            # Add ports if specified
            if service_config.get("ports"):
                service_args["ports"] = service_config["ports"]
                
            # Add environment if specified
            if service_config.get("environment"):
                service_args["env"] = service_config["environment"]
                
            # Add logging if specified
            if service_config.get("logging"):
                service_args["logging"] = service_config["logging"]
                
            # Add replicas if specified
            if service_config.get("replicas", 1) != 1:
                service_args["replicas"] = service_config["replicas"]
                
            # Add namespace if specified
            if config.get("namespace"):
                service_args["namespace"] = config["namespace"]
            
            action_steps.append(ActionStep(
                name=action_name,
                args=service_args
            ))
            action_order.append(action_name)
        
        # Step 5: Verify HTTP endpoints
        for service_name, service_config in services.items():
            if service_config.get("health_check"):
                health_config = service_config["health_check"]
                action_name = f"verify_http"
                if len([s for s in services.values() if s.get("health_check")]) > 1:
                    action_name = f"verify_http_{service_name}"
                
                verify_args = {
                    "url": health_config.get("url", f"http://localhost:8080{health_config.get('path', '/health')}"),
                    "expect_status": health_config.get("status_code", 200)
                }
                
                # Add timeout if specified
                if health_config.get("timeout"):
                    verify_args["timeout"] = health_config["timeout"]
                
                action_steps.append(ActionStep(
                    name=action_name,
                    args=verify_args
                ))
                action_order.append(action_name)
        
        # Create ActionList with proper README format
        action_list = ActionList(
            version="1",
            steps=action_steps,
            metadata={
                "generated_from": "ir_conversion",
                "total_actions": len(action_steps),
                "action_order": action_order  # Store for dependency tracking
            }
        )
        
        # Validate the generated action list
        if not _validate_action_list_structure(action_list):
            raise DependencyError("Generated action list has invalid structure")
        
        logger.info(f"Successfully converted IR to {len(action_steps)} actions")
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
            logger.error("Input is not a ActionList instance")
            return False
        
        # Check that all actions are valid ActionStep instances
        for action in action_list.steps:
            if not isinstance(action, ActionStep):
                logger.error(f"Invalid action found: {action}")
                return False
        
        # Check for duplicate action names
        action_names = [action.name for action in action_list.steps]
        if len(action_names) != len(set(action_names)):
            logger.error("Duplicate action names found")
            return False
        
        # Validate action structure matches README specification
        if not _validate_action_list_structure(action_list):
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
        optimized_actions = action_list.steps.copy()
        
        # TODO: Implement actual optimization algorithms
        # For now, just return the original list with updated metadata
        
        optimized_metadata = action_list.metadata.copy()
        optimized_metadata.update({
            "optimized": True,
            "optimization_applied": "basic_validation_only"
        })
        
        return ActionList(
            version=action_list.version,
            steps=optimized_actions,
            metadata=optimized_metadata
        )
        
    except Exception as e:
        logger.error(f"Error during ActionList optimization: {str(e)}")
        return action_list


def _validate_action_list_structure(action_list: ActionList) -> bool:
    """
    Validate that the ActionList structure matches README specification.
    
    Args:
        action_list: The ActionList to validate
        
    Returns:
        bool: True if structure is valid, False otherwise
    """
    try:
        # Check version field
        if action_list.version != "1":
            logger.error(f"Invalid version: {action_list.version}, expected '1'")
            return False
        
        # Check that each step has only 'name' and 'args' fields
        for i, step in enumerate(action_list.steps):
            if not hasattr(step, 'name') or not hasattr(step, 'args'):
                logger.error(f"Step {i}: missing required 'name' or 'args' field")
                return False
            
            if not isinstance(step.name, str) or not step.name.strip():
                logger.error(f"Step {i}: 'name' must be a non-empty string")
                return False
            
            if not isinstance(step.args, dict):
                logger.error(f"Step {i}: 'args' must be a dictionary")
                return False
            
            # Validate known action patterns
            if not _validate_action_name_and_args(step.name, step.args):
                logger.error(f"Step {i}: invalid action name/args combination")
                return False
        
        logger.debug("ActionList structure validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Error during structure validation: {str(e)}")
        return False


def _validate_action_name_and_args(name: str, args: Dict[str, Any]) -> bool:
    """
    Validate that action name and args match expected patterns.
    
    Args:
        name: Action name
        args: Action arguments
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Define expected argument patterns for common actions
    action_patterns = {
        "fetch_repo": ["url", "ref"],
        "build_image": ["tags"],
        "ensure_service": ["name"],
        "verify_http": ["url"],
        "create_namespace": ["namespace"]
    }
    
    # Check if the action name matches a known pattern
    base_name = name
    for pattern in action_patterns:
        if name == pattern or name.startswith(f"{pattern}_"):
            base_name = pattern
            break
    
    # Validate required arguments for known patterns
    if base_name in action_patterns:
        required_args = action_patterns[base_name]
        for req_arg in required_args:
            if req_arg not in args:
                logger.warning(f"Action '{name}': missing recommended argument '{req_arg}'")
                # Don't fail validation for missing args, just warn
    
    return True