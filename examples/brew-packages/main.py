"""
Homebrew Package Example - Install macOS packages via Homebrew.

This example demonstrates the AI completion architecture where you provide
minimal information and the AI intelligently completes all fields.
"""

from clockwork.resources import BrewPackageResource

# Minimal - AI completes everything (name, packages, cask)
dev_tools = BrewPackageResource(
    description="essential development tools like jq and htop"
)

# AI determines it's a GUI app and sets cask=True
code_editor = BrewPackageResource(
    description="Visual Studio Code editor"
)

# Override specific fields if needed
network_utils = BrewPackageResource(
    description="network diagnostic tools",
    packages=["curl", "nmap"]  # Explicit packages, AI fills in name and cask
)
