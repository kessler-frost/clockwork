"""
Git Repository Example - Clone repositories with AI completion.

This example demonstrates the AI completion architecture where you provide
minimal information and the AI intelligently finds repos and completes all fields.
"""

from clockwork.resources import GitRepoResource

# Minimal - AI finds repo URL, picks dest and branch
fastapi_repo = GitRepoResource(
    description="FastAPI Python web framework repository"
)

# AI suggests everything based on description
flask_repo = GitRepoResource(
    description="Python Flask web framework"
)

# Override specific fields if needed
awesome_python = GitRepoResource(
    description="curated list of awesome Python frameworks and libraries",
    dest="scratch/awesome"  # Custom destination, AI fills name, repo_url, branch
)
