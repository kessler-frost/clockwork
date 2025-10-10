"""
Development Environment Setup - Complete Mac development environment.

This example demonstrates a real-world scenario combining all Clockwork resources:
- Install development tools via Homebrew
- Clone project repositories
- Create project directory structure
- Generate configuration files
- Deploy local services (Docker)

This creates a complete, reproducible development environment on macOS.
"""

from clockwork.resources import (
    FileResource,
    DockerServiceResource,
    GitRepoResource,
    BrewPackageResource,
    DirectoryResource,
    ArtifactSize,
)
from clockwork.assertions import (
    FileExistsAssert,
    FileSizeAssert,
    FileContentMatchesAssert,
    FilePermissionsAssert,
    ContainerRunningAssert,
    PortAccessibleAssert,
    HealthcheckAssert,
)

# =============================================================================
# 1. INSTALL DEVELOPMENT TOOLS
# =============================================================================
# Install essential command-line tools via Homebrew
# These tools are commonly needed for modern web development
dev_tools = BrewPackageResource(
    name="dev-tools",
    description="Essential development tools",
    packages=["jq", "git", "tree"],  # JSON processor, version control, directory visualizer
    update=True,  # Update Homebrew before installing
)

# =============================================================================
# 2. CREATE PROJECT DIRECTORY STRUCTURE
# =============================================================================
# Organize project files in a clean, structured way
# This mirrors a typical application architecture

# Root directory for the development environment
project_root = DirectoryResource(
    name="project-root",
    description="Main project directory",
    path="scratch/devenv",
    mode="755",  # rwxr-xr-x - standard directory permissions
    assertions=[
        FileExistsAssert(path="scratch/devenv"),
        FilePermissionsAssert(
            path="scratch/devenv",
            mode="755",
        ),
    ]
)

# Source code directory
src_dir = DirectoryResource(
    name="src-directory",
    description="Source code directory",
    path="scratch/devenv/src",
    mode="755",
    assertions=[
        FileExistsAssert(path="scratch/devenv/src"),
    ]
)

# Data directory with restricted permissions for sensitive data
data_dir = DirectoryResource(
    name="data-directory",
    description="Data storage directory",
    path="scratch/devenv/data",
    mode="700",  # rwx------ - only owner can read/write/execute
    assertions=[
        FileExistsAssert(path="scratch/devenv/data"),
        FilePermissionsAssert(
            path="scratch/devenv/data",
            mode="700",
        ),
    ]
)

# Configuration directory
config_dir = DirectoryResource(
    name="config-directory",
    description="Configuration files directory",
    path="scratch/devenv/config",
    mode="755",
    assertions=[
        FileExistsAssert(path="scratch/devenv/config"),
    ]
)

# Logs directory
logs_dir = DirectoryResource(
    name="logs-directory",
    description="Application logs directory",
    path="scratch/devenv/logs",
    mode="755",
    assertions=[
        FileExistsAssert(path="scratch/devenv/logs"),
    ]
)

# =============================================================================
# 3. CLONE PROJECT REPOSITORIES
# =============================================================================
# Clone real-world projects to work with

# Clone a sample Python web application
app_repo = GitRepoResource(
    name="app-repo",
    description="Clone a lightweight Python web application repository for testing",
    repo_url="https://github.com/tiangolo/fastapi.git",  # FastAPI - popular Python framework
    dest="scratch/devenv/src/fastapi",
    branch="master",
    assertions=[
        FileExistsAssert(path="scratch/devenv/src/fastapi"),
        FileExistsAssert(path="scratch/devenv/src/fastapi/.git"),
    ]
)

# Clone a frontend framework for full-stack development
frontend_repo = GitRepoResource(
    name="frontend-repo",
    description="Clone a modern frontend framework repository",
    repo_url="https://github.com/vuejs/core.git",  # Vue.js core
    dest="scratch/devenv/src/vue",
    branch="main",
    assertions=[
        FileExistsAssert(path="scratch/devenv/src/vue"),
        FileExistsAssert(path="scratch/devenv/src/vue/.git"),
    ]
)

# =============================================================================
# 4. GENERATE CONFIGURATION FILES
# =============================================================================
# Create essential configuration files for the development environment

# Environment variables file
env_file = FileResource(
    name=".env",
    description="Environment configuration for development",
    content="""# Development Environment Variables
# Database connection
DATABASE_URL=postgresql://devuser:devpassword@localhost:5432/devdb
DATABASE_POOL_SIZE=10

# Redis cache
REDIS_URL=redis://localhost:6379
REDIS_MAX_CONNECTIONS=20

# Application settings
DEBUG=true
LOG_LEVEL=info
SECRET_KEY=dev-secret-key-change-in-production

# API settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# External services
SMTP_HOST=localhost
SMTP_PORT=1025
""",
    directory="scratch/devenv",
    assertions=[
        FileExistsAssert(path="scratch/devenv/.env"),
        FileContentMatchesAssert(
            path="scratch/devenv/.env",
            pattern="DATABASE_URL"
        ),
    ]
)

# Docker Compose configuration for local development
docker_compose = FileResource(
    name="docker-compose.yml",
    description="Generate a comprehensive docker-compose.yml file for local development with PostgreSQL, Redis, and common development services",
    size=ArtifactSize.MEDIUM,
    directory="scratch/devenv",
    assertions=[
        FileExistsAssert(path="scratch/devenv/docker-compose.yml"),
        FileSizeAssert(
            path="scratch/devenv/docker-compose.yml",
            min_bytes=200,
            max_bytes=10000
        ),
    ]
)

# Python requirements file
requirements_file = FileResource(
    name="requirements.txt",
    description="Generate a comprehensive requirements.txt file for a modern Python web application including FastAPI, SQLAlchemy, Redis, testing tools, and development dependencies",
    size=ArtifactSize.SMALL,
    directory="scratch/devenv",
    assertions=[
        FileExistsAssert(path="scratch/devenv/requirements.txt"),
        FileContentMatchesAssert(
            path="scratch/devenv/requirements.txt",
            pattern="fastapi"
        ),
    ]
)

# Makefile for common development tasks
makefile = FileResource(
    name="Makefile",
    description="Generate a comprehensive Makefile with common development tasks: install dependencies, run tests, start/stop services, database migrations, code formatting, linting, and cleanup tasks",
    size=ArtifactSize.MEDIUM,
    directory="scratch/devenv",
    assertions=[
        FileExistsAssert(path="scratch/devenv/Makefile"),
        FileSizeAssert(
            path="scratch/devenv/Makefile",
            min_bytes=100,
            max_bytes=5000
        ),
    ]
)

# Git ignore file
gitignore = FileResource(
    name=".gitignore",
    description="Generate a comprehensive .gitignore file for Python and Node.js projects including common IDE files, build artifacts, logs, and environment files",
    size=ArtifactSize.SMALL,
    directory="scratch/devenv",
    assertions=[
        FileExistsAssert(path="scratch/devenv/.gitignore"),
        FileContentMatchesAssert(
            path="scratch/devenv/.gitignore",
            pattern="__pycache__"
        ),
    ]
)

# README with comprehensive setup instructions
readme = FileResource(
    name="README.md",
    description="Write a comprehensive README for this development environment explaining: what services are running, how to get started, available make commands, project structure, database setup, testing instructions, and troubleshooting tips",
    size=ArtifactSize.LARGE,
    directory="scratch/devenv",
    assertions=[
        FileExistsAssert(path="scratch/devenv/README.md"),
        FileSizeAssert(
            path="scratch/devenv/README.md",
            min_bytes=500,
            max_bytes=50000
        ),
        FileContentMatchesAssert(
            path="scratch/devenv/README.md",
            pattern="Development Environment"
        ),
    ]
)

# =============================================================================
# 5. DEPLOY LOCAL SERVICES (DOCKER)
# =============================================================================
# Spin up essential backend services for development

# PostgreSQL database for application data
postgres_db = DockerServiceResource(
    name="dev-postgres",
    description="PostgreSQL database for development",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_USER": "devuser",
        "POSTGRES_PASSWORD": "devpassword",
        "POSTGRES_DB": "devdb",
    },
    volumes=["postgres_data:/var/lib/postgresql/data"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=15),
        PortAccessibleAssert(
            port=5432,
            host="localhost",
            protocol="tcp"
        ),
    ]
)

# Redis cache for sessions and caching
redis_cache = DockerServiceResource(
    name="dev-redis",
    description="Redis cache for development",
    image="redis:7-alpine",
    ports=["6379:6379"],
    volumes=["redis_data:/data"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(
            port=6379,
            host="localhost",
            protocol="tcp"
        ),
    ]
)

# Nginx reverse proxy for local development
nginx_proxy = DockerServiceResource(
    name="dev-nginx",
    description="Nginx reverse proxy for local development",
    image="nginx:alpine",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(
            port=8080,
            host="localhost",
            protocol="tcp"
        ),
        HealthcheckAssert(
            url="http://localhost:8080",
            expected_status=200,
            timeout_seconds=5
        ),
    ]
)

# =============================================================================
# Complete development environment ready to use!
# =============================================================================
