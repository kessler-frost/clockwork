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
        files = ir_data.get("files", {})
        directories = ir_data.get("directories", {})
        verifications = ir_data.get("verifications", {})
        checks = ir_data.get("checks", {})

        logger.debug(f"Planner received: {len(services)} services, {len(files)} files, {len(directories)} directories, {len(verifications)} verifications, {len(checks)} checks")
        
        # Keep track of action ordering for dependency resolution
        action_order = []
        dependency_map = {}
        
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
        
        # Step 3: Handle directory operations
        for directory_name, directory_config in directories.items():
            action_name = f"create_directory"
            if len(directories) > 1:
                action_name = f"create_directory_{directory_name}"

            directory_args = {
                "name": directory_config.get("name", directory_name),
                "path": directory_config.get("path", ""),
                "mode": directory_config.get("mode", "755"),
                "description": directory_config.get("description", "Directory resource")
            }

            action_steps.append(ActionStep(
                name=action_name,
                type=ActionType.CREATE_DIRECTORY,
                args=directory_args
            ))
            action_order.append(action_name)

            # Track dependencies
            if directory_config.get("depends_on"):
                dependency_map[action_name] = directory_config["depends_on"]

        # Step 4: Handle file operations
        for file_name, file_config in files.items():
            action_name = f"file_operation"
            if len(files) > 1:
                action_name = f"file_operation_{file_name}"

            file_args = {
                "name": file_config.get("name", file_name),
                "path": file_config.get("path", ""),
                "type": file_config.get("type", "file"),  # file, directory
                "mode": file_config.get("mode", "644")
            }

            # Add content if specified
            if file_config.get("content"):
                file_args["content"] = file_config["content"]

            action_steps.append(ActionStep(
                name=action_name,
                type=ActionType.FILE_OPERATION,
                args=file_args
            ))
            action_order.append(action_name)

            # Track dependencies
            if file_config.get("depends_on"):
                dependency_map[action_name] = file_config["depends_on"]
        
        # Step 5: Build images
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
                    type=ActionType.BUILD_IMAGE,
                    args=build_args
                ))
                action_order.append(action_name)

        # Step 6: Ensure services are running
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
                type=ActionType.ENSURE_SERVICE,
                args=service_args
            ))
            action_order.append(action_name)
            
            # Track dependencies
            if service_config.get("depends_on"):
                dependency_map[action_name] = service_config["depends_on"]
        
        # Step 7: Handle verification checks
        for verification_name, verification_config in verifications.items():
            action_name = f"verification"
            if len(verifications) > 1:
                action_name = f"verification_{verification_name}"

            verification_args = {
                "name": verification_config.get("name", verification_name),
                "checks": verification_config.get("checks", [])
            }

            action_steps.append(ActionStep(
                name=action_name,
                type=ActionType.VERIFY_CHECK,
                args=verification_args
            ))
            action_order.append(action_name)

            # Track dependencies
            if verification_config.get("depends_on"):
                dependency_map[action_name] = verification_config["depends_on"]

        # Step 8: Handle check resources
        for check_name, check_config in checks.items():
            action_name = f"check"
            if len(checks) > 1:
                action_name = f"check_{check_name}"

            check_args = {
                "name": check_config.get("name", check_name),
                "description": check_config.get("description", "Check resource verification"),
                "type": check_config.get("type", "file_exists"),
                "target": check_config.get("target", "")
            }

            action_steps.append(ActionStep(
                name=action_name,
                type=ActionType.VERIFY_CHECK,
                args=check_args
            ))
            action_order.append(action_name)

            # Track dependencies
            if check_config.get("depends_on"):
                dependency_map[action_name] = check_config["depends_on"]

        # Step 9: Verify HTTP endpoints
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
                    type=ActionType.VERIFY_HTTP,
                    args=verify_args
                ))
                action_order.append(action_name)
        
        # Apply dependency sorting to ensure proper execution order
        if dependency_map:
            action_steps = _resolve_dependencies(action_steps, dependency_map)
        
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


# optimize_action_list function removed - was only placeholder implementation


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
        "create_namespace": ["namespace"],
        "file_operation": ["name", "path"],
        "create_directory": ["name", "path"],
        "verification": ["name", "checks"],
        "check": ["name", "description"]
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


def _resolve_dependencies(action_steps: List[ActionStep], dependency_map: Dict[str, List[str]]) -> List[ActionStep]:
    """
    Sort action steps based on their dependencies.
    
    Args:
        action_steps: List of action steps to sort
        dependency_map: Map of action names to their dependencies
        
    Returns:
        Sorted list of action steps
        
    Raises:
        DependencyError: If circular dependencies are detected
    """
    # Create a mapping from action name to ActionStep for easy lookup
    action_by_name = {action.name: action for action in action_steps}
    
    # Create a simplified dependency graph using action names
    resolved = []
    visited = set()
    visiting = set()
    
    def visit(action_name: str):
        if action_name in visiting:
            raise DependencyError(f"Circular dependency detected involving '{action_name}'")
        
        if action_name in visited:
            return
            
        visiting.add(action_name)
        
        # Visit dependencies first
        if action_name in dependency_map:
            for dep in dependency_map[action_name]:
                # Convert resource reference to action name
                dep_action_name = _convert_resource_ref_to_action_name(dep, list(action_by_name.keys()))
                if dep_action_name and dep_action_name in action_by_name:
                    visit(dep_action_name)
        
        visiting.remove(action_name)
        visited.add(action_name)
        
        # Add to resolved list if the action exists
        if action_name in action_by_name:
            resolved.append(action_by_name[action_name])
    
    # Visit all actions
    for action in action_steps:
        if action.name not in visited:
            visit(action.name)
    
    return resolved


def _convert_resource_ref_to_action_name(resource_ref: str, action_names: List[str]) -> Optional[str]:
    """
    Convert a resource reference like 'file.demo_directory' to the corresponding action name.
    
    Args:
        resource_ref: Resource reference (e.g., 'file.demo_directory')
        action_names: List of available action names
        
    Returns:
        Corresponding action name or None if not found
    """
    if '.' not in resource_ref:
        return resource_ref
    
    resource_type, resource_name = resource_ref.split('.', 1)
    
    # Map resource types to action prefixes
    type_mapping = {
        'file': 'file_operation',
        'directory': 'create_directory',
        'service': 'ensure_service',
        'verification': 'verification',
        'check': 'check'
    }
    
    if resource_type in type_mapping:
        action_prefix = type_mapping[resource_type]
        
        # Try exact match first
        candidate_name = f"{action_prefix}_{resource_name}"
        if candidate_name in action_names:
            return candidate_name
        
        # Try without suffix if only one of this type
        if action_prefix in action_names:
            return action_prefix
    
    return None