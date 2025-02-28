#!/usr/bin/env python3
"""
Installer script for the Claude PR Reviewer git hook.
This script installs the pre-push hook in the current git repository.
"""

import os
import sys
import stat
import shutil
import subprocess
from pathlib import Path


def get_git_root() -> str:
    """Get the root directory of the git repository"""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            universal_newlines=True
        ).strip()
    except subprocess.CalledProcessError:
        print("Error: Not a git repository")
        sys.exit(1)


def create_hook_file(hooks_dir: str, script_path: str) -> None:
    """Create the pre-push hook file"""
    hook_path = os.path.join(hooks_dir, "pre-push")
    
    # Create the hook file content
    hook_content = f"""#!/bin/sh
# Claude PR Reviewer pre-push hook
# This hook runs the Claude PR Reviewer before pushing commits

# Run the PR reviewer script
python3 "{script_path}" "$@"

# Check the exit code
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo "Push cancelled by Claude PR Reviewer."
    exit $exit_code
fi
"""
    
    # Write the hook file
    with open(hook_path, "w") as f:
        f.write(hook_content)
    
    # Make the hook executable
    os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    print(f"Pre-push hook installed at: {hook_path}")


def install_dependencies() -> None:
    """Install required Python dependencies"""
    try:
        print("Installing required Python dependencies...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "requests"
        ])
        print("Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("Error: Failed to install dependencies")
        sys.exit(1)


def main() -> None:
    """Main function to install the git hook"""
    # Find the git hooks directory
    git_root = get_git_root()
    hooks_dir = os.path.join(git_root, ".git", "hooks")
    
    # Ensure hooks directory exists
    if not os.path.isdir(hooks_dir):
        os.makedirs(hooks_dir)
    
    # Get the script path
    current_script = os.path.abspath(__file__)
    script_dir = os.path.dirname(current_script)
    
    # Copy the reviewer script to the git repository
    reviewer_script = os.path.join(script_dir, "claude_pr_reviewer.py")
    destination_script = os.path.join(git_root, ".git", "hooks", "claude_pr_reviewer.py")
    
    if os.path.exists(os.path.join(script_dir, "claude_pr_reviewer.py")):
        shutil.copy2(reviewer_script, destination_script)
        os.chmod(destination_script, os.stat(destination_script).st_mode | stat.S_IXUSR)
    else:
        print("Error: claude_pr_reviewer.py not found in the same directory as this script")
        sys.exit(1)
    
    # Create the pre-push hook
    create_hook_file(hooks_dir, destination_script)
    
    # Install required dependencies
    install_dependencies()
    
    print("Claude PR Reviewer hook installed successfully!")
    print("\nNote: To use this hook, you need to set your Claude API key using either:")
    print("1. Export environment variable: export CLAUDE_API_KEY=your_api_key")
    print("2. The first time you push, you'll be prompted to enter your API key")


if __name__ == "__main__":
    main()