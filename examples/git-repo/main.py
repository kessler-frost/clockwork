"""
Git Repository Example - Clone repositories with optional AI-suggested URLs.

This example demonstrates:
- GitRepoResource with AI-suggested repository URL
- GitRepoResource with explicit repository URL
- Different branches and pull configurations
- Default assertions for Git repository validation
"""

from clockwork.resources import GitRepoResource

# AI suggests repo URL based on description
pyinfra_repo = GitRepoResource(
    name="pyinfra-docs",
    description="Clone the PyInfra documentation repository",
    dest="scratch/repos/pyinfra",
    branch="main",
)

# AI suggests a popular Python web framework repository
flask_repo = GitRepoResource(
    name="flask-framework",
    description="Python Flask web framework source code",
    dest="scratch/repos/flask",
    branch="main",
    pull=True,
)

# Explicit repo URL with specific branch
clockwork_demo = GitRepoResource(
    name="awesome-python",
    description="A curated list of awesome Python frameworks, libraries and resources",
    repo_url="https://github.com/vinta/awesome-python.git",
    dest="scratch/repos/awesome-python",
    branch="master",
    pull=True,
)
