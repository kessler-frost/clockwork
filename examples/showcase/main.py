"""
Clockwork Showcase - Comprehensive feature demonstration.

This example demonstrates all major Clockwork capabilities in one place:
- File creation (manual and AI-generated)
- Template rendering (manual and AI-generated)
- Git repository cloning
- Docker containers with assertions
- Tool integration (web search and custom functions)

Run: clockwork apply
Validate: clockwork assert
Cleanup: clockwork destroy
"""

from datetime import datetime
from clockwork.resources import (
    FileResource,
    TemplateFileResource,
    GitRepoResource,
    DockerResource,
)
from clockwork.assertions import (
    FileExistsAssert,
    FileContentMatchesAssert,
    ContainerRunningAssert,
    PortAccessibleAssert,
    HealthcheckAssert,
)
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool


# ==============================================================================
# SECTION 1: File Resources
# ==============================================================================

# Manual file creation - you provide all content
readme_manual = FileResource(
    name="README.md",
    description="Project README with getting started instructions",
    directory="scratch",
    content="""# Clockwork Showcase

This demonstrates Clockwork's infrastructure orchestration capabilities.

## Features
- Declarative Python infrastructure
- AI-powered resource completion
- Pulumi-based deployment
- Type-safe assertions

See main.py for the complete example.
""",
    mode="644",
    assertions=[
        FileExistsAssert(path="scratch/README.md"),
        FileContentMatchesAssert(path="scratch/README.md", pattern="Clockwork"),
    ]
)

# AI-generated file - AI creates content from description
config_ai = FileResource(
    name="config.yaml",
    description="Application configuration file with database settings (host: localhost, port: 5432, name: appdb) and Redis cache (host: localhost, port: 6379)",
    directory="scratch",
    # No content specified - AI generates it!
    assertions=[
        FileExistsAssert(path="scratch/config.yaml"),
        FileContentMatchesAssert(path="scratch/config.yaml", pattern="5432"),
    ]
)


# ==============================================================================
# SECTION 2: Template Resources
# ==============================================================================

# Manual template - you provide template and variables
nginx_config_manual = TemplateFileResource(
    name="nginx.conf",
    description="Nginx configuration for web server on port 8080",
    directory="scratch",
    template_content="""server {
    listen {{ port }};
    server_name {{ server_name }};

    location / {
        root {{ document_root }};
        index index.html;
    }
}""",
    variables={
        "port": 8080,
        "server_name": "localhost",
        "document_root": "/var/www/html"
    },
    mode="644",
    assertions=[
        FileExistsAssert(path="scratch/nginx.conf"),
        FileContentMatchesAssert(path="scratch/nginx.conf", pattern="8080"),
    ]
)

# AI-generated template - AI creates template and variables from description
redis_config_ai = TemplateFileResource(
    name="redis.conf",
    description="Redis configuration file for cache server with 256MB max memory, LRU eviction policy, and persistence enabled",
    directory="scratch",
    # AI generates both template_content and variables!
    assertions=[
        FileExistsAssert(path="scratch/redis.conf"),
    ]
)


# ==============================================================================
# SECTION 3: Git Repository Resources
# ==============================================================================

# AI finds the repository URL from description
# Note: FastAPI uses 'master' branch, so we specify it explicitly
fastapi_repo = GitRepoResource(
    description="FastAPI Python web framework repository",
    dest="scratch/repos/fastapi",
    branch="master"  # Specify branch to avoid AI guessing wrong
    # AI fills in: name, repo_url
)


# ==============================================================================
# SECTION 4: Docker Container Resources
# ==============================================================================

# Docker container with comprehensive assertions
nginx_container = DockerResource(
    name="nginx-showcase",
    description="Nginx web server for testing",
    image="nginx:alpine",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8080, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8080", expected_status=200, timeout_seconds=5),
    ]
)


# ==============================================================================
# SECTION 5: Tool Integration (Optional)
# ==============================================================================

# Custom tool - Python function the AI can call
def get_current_time(format_type: str) -> str:
    """Get current system time in various formats.

    Args:
        format_type: Format type ('time', 'date', or 'datetime')

    Returns:
        Formatted timestamp string
    """
    now = datetime.now()
    if format_type == 'time':
        return now.strftime('%H:%M:%S')
    elif format_type == 'date':
        return now.strftime('%Y-%m-%d')
    else:
        return now.strftime('%Y-%m-%d %H:%M:%S')


# Uncomment to enable tool examples (requires API key with web search)
#
# web_search_report = FileResource(
#     name="ai_trends.md",
#     description="Brief summary of latest AI infrastructure trends in 2024",
#     directory="scratch",
#     tools=[duckduckgo_search_tool()],
#     assertions=[
#         FileExistsAssert(path="scratch/ai_trends.md"),
#         FileContentMatchesAssert(path="scratch/ai_trends.md", pattern="AI"),
#     ]
# )
#
# custom_tool_report = FileResource(
#     name="timestamp_report.md",
#     description="System report with current date, time, and welcome message",
#     directory="scratch",
#     tools=[get_current_time],
#     assertions=[
#         FileExistsAssert(path="scratch/timestamp_report.md"),
#         FileContentMatchesAssert(path="scratch/timestamp_report.md", pattern=r"\d{4}-\d{2}-\d{2}"),
#     ]
# )
