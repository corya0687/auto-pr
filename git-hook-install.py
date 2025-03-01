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

# Get the directory where the script is located
SCRIPT_DIR="$(dirname "$0")"

# Add the hooks directory to Python path to find the claude_pr_reviewer package
PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH" python3 "{script_path}" "$@"

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
        # First install required packages
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "requests"
        ])
        
        # Try to install PyQt5, but don't fail if it can't be installed
        try:
            print("Attempting to install PyQt5 for GUI...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "PyQt5"
            ])
            print("PyQt5 installed successfully")
        except subprocess.CalledProcessError:
            print("Note: PyQt5 could not be installed. Will use terminal UI instead.")
            
        print("Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("Error: Failed to install core dependencies")
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
        # Copy the main script
        shutil.copy2(reviewer_script, destination_script)
        os.chmod(destination_script, os.stat(destination_script).st_mode | stat.S_IXUSR)
        
        # Also copy the claude_pr_reviewer package directory
        package_source = os.path.join(script_dir, "claude_pr_reviewer")
        package_dest = os.path.join(git_root, ".git", "hooks", "claude_pr_reviewer")
        
        # Create the package directory if it doesn't exist
        if not os.path.exists(package_dest):
            os.makedirs(package_dest)
        
        # Copy all files from the package
        if os.path.isdir(package_source):
            for item in os.listdir(package_source):
                item_src = os.path.join(package_source, item)
                item_dst = os.path.join(package_dest, item)
                
                if os.path.isdir(item_src):
                    # It's a subdirectory, copy it recursively
                    if not os.path.exists(item_dst):
                        os.makedirs(item_dst)
                    for subitem in os.listdir(item_src):
                        subitem_src = os.path.join(item_src, subitem)
                        subitem_dst = os.path.join(item_dst, subitem)
                        if os.path.isfile(subitem_src):
                            shutil.copy2(subitem_src, subitem_dst)
                elif os.path.isfile(item_src):
                    # It's a file, just copy it
                    shutil.copy2(item_src, item_dst)
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