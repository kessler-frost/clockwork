"""
Docker Service Example - Deploy a simple web service.

This example demonstrates DockerServiceResource with AI-suggested image.
"""

from clockwork.resources import DockerServiceResource

# Simple web service - AI will suggest an appropriate image
api = DockerServiceResource(
    name="clockwork-demo",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"]
)
