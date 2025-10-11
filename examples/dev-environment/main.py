"""
Development Environment Setup - Complete Mac development environment.

This example demonstrates the power of AI completion - creating a complete,
production-ready development environment with minimal code. The AI intelligently
completes all missing fields based on simple descriptions.

Previous version: 336 lines
This version: ~80 lines
Functionality: Identical!
"""

from clockwork.resources import (
    FileResource,
    AppleContainerResource,
    GitRepoResource,
    BrewPackageResource,
    DirectoryResource,
)

# =============================================================================
# 1. INSTALL DEVELOPMENT TOOLS
# =============================================================================
# AI determines packages: jq, git, tree, wget, curl
dev_tools = BrewPackageResource(
    description="essential command-line development tools"
)

# =============================================================================
# 2. CREATE PROJECT DIRECTORY STRUCTURE
# =============================================================================
# AI generates appropriate names and picks secure permissions
project_root = DirectoryResource(
    description="Main project directory",
    path="scratch/devenv"
)

src_dir = DirectoryResource(
    description="Source code directory",
    path="scratch/devenv/src"
)

data_dir = DirectoryResource(
    description="Data storage with restricted access",
    path="scratch/devenv/data"
)

# =============================================================================
# 3. CLONE PROJECT REPOSITORIES
# =============================================================================
# AI finds repo URLs, picks destinations and branches
fastapi_repo = GitRepoResource(
    description="FastAPI Python web framework"
)

vue_repo = GitRepoResource(
    description="Vue.js frontend framework"
)

# =============================================================================
# 4. GENERATE CONFIGURATION FILES
# =============================================================================
# AI generates comprehensive, production-ready configs
env_file = FileResource(
    description="Environment variables for PostgreSQL, Redis, and API configuration",
    directory="scratch/devenv"
)

docker_compose = FileResource(
    description="docker-compose.yml with PostgreSQL, Redis, and development services",
    directory="scratch/devenv"
)

requirements = FileResource(
    description="requirements.txt with FastAPI, SQLAlchemy, Redis, and testing tools",
    directory="scratch/devenv"
)

makefile = FileResource(
    description="Makefile with tasks for install, test, start/stop services, migrations, and cleanup",
    directory="scratch/devenv"
)

readme = FileResource(
    description="README explaining the dev environment, services, setup instructions, and commands",
    directory="scratch/devenv"
)

# =============================================================================
# 5. DEPLOY LOCAL SERVICES (APPLE CONTAINERS)
# =============================================================================
# AI suggests images, ports, volumes, and environment variables
postgres_db = AppleContainerResource(
    description="PostgreSQL database for development"
)

redis_cache = AppleContainerResource(
    description="Redis cache for sessions and caching"
)

nginx_proxy = AppleContainerResource(
    description="Nginx reverse proxy for local development"
)

# =============================================================================
# Complete development environment ready to use!
# Run: clockwork apply
# =============================================================================
