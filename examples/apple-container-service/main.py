"""
Apple Container Service Example - AI completes everything from a description.

This example demonstrates the power of Clockwork's minimal API:
- Just describe what you want, AI handles the rest
- One minimal example (just description)
- One advanced example (description + overrides + assertions)
"""

from clockwork.resources import AppleContainerResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
)

# MINIMAL - Just describe what you want!
# AI completes: name, image, ports, volumes, env_vars, networks
minimal = AppleContainerResource(
    description="lightweight nginx web server for testing"
)
# AI generates something like:
#   name="nginx-server"
#   image="nginx:alpine"
#   ports=["80:80"]
#   volumes=[]
#   env_vars={}
#   networks=[]

# ADVANCED - Override specifics and add assertions
# AI completes missing fields: name, image, volumes, env_vars, networks
api = AppleContainerResource(
    description="lightweight web server for testing and demos",
    ports=["8090:80"],  # Override port mapping
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8090, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8090", expected_status=200, timeout_seconds=5),
    ]
)
# AI generates something like:
#   name="nginx-demo"
#   image="nginx:alpine"
#   ports=["8090:80"]  # User override kept
#   volumes=[]
#   env_vars={}
#   networks=[]
