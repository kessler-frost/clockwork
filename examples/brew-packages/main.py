"""
Homebrew Package Example - Install macOS packages via Homebrew.

This example demonstrates:
- BrewPackageResource with AI-suggested packages (description only)
- BrewPackageResource with explicit package list
- Installing GUI apps via Homebrew cask
- Package updates and state management
"""

from clockwork.resources import BrewPackageResource

# AI suggests packages based on description
dev_tools = BrewPackageResource(
    name="dev-tools",
    description="Install essential command-line development tools like jq for JSON processing, htop for system monitoring, and wget for downloading files",
    update=True,
)

# Explicit package list
networking_tools = BrewPackageResource(
    name="networking-tools",
    description="Network utilities",
    packages=["curl", "nmap", "telnet"],
    present=True,
)

# GUI app via cask
visual_tools = BrewPackageResource(
    name="visual-studio-code",
    description="Code editor",
    packages=["visual-studio-code"],
    cask=True,
)
