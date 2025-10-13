"""
Docker Service Example - AI completes everything from a description.

This example demonstrates the power of Clockwork's minimal API:
- Just describe what you want, AI handles the rest
- Includes a template file example for nginx configuration
- One minimal example (just description)
- One advanced example (description + overrides + assertions)
"""

from clockwork.resources import DockerResource, TemplateFileResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
    FileExistsAssert,
)

# Example 1: Template file for nginx configuration
nginx_config = TemplateFileResource(
    description="Nginx configuration file that serves on port 8091 and serves files from /usr/share/nginx/html",
    template_content="""server {
    listen {{ port }};
    server_name {{ server_name }};

    location / {
        root {{ document_root }};
        index index.html;
    }
}""",
    variables={
        "port": 8091,
        "server_name": "localhost",
        "document_root": "/usr/share/nginx/html"
    },
    name="nginx.conf",
    directory="scratch",
    mode="644",
    assertions=[
        FileExistsAssert(path="scratch/nginx.conf"),
    ]
)

# Example 2: Docker container (simplified - no need for empty values!)
nginx_web = DockerResource(
    description="lightweight nginx web server for testing",
    name="nginx-web",
    image="nginx:alpine",
    ports=["8091:80"],
    # volumes, env_vars, networks default to empty - no need to specify!
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8091, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8091", expected_status=200, timeout_seconds=5),
    ]
)
