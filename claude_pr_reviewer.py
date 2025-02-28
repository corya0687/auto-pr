#!/usr/bin/env python3
"""
Claude PR Reviewer - A git hook application that uses Claude AI to review PRs
and displays comments in a GUI before allowing a push.
"""

import sys
import os

from claude_pr_reviewer.interfaces import GitInterface, AIReviewerInterface, UserInterfaceInterface
from claude_pr_reviewer.git import GitCLI
from claude_pr_reviewer.ai import ClaudeAIReviewer
from claude_pr_reviewer.ui import PyQtUI, TerminalUI, GUI_TOOLKIT
from claude_pr_reviewer.config_manager import ConfigManager
from claude_pr_reviewer.pr_reviewer import PRReviewer


def main() -> int:
    """Main entry point for pre-push hook"""
    try:
        # Initialize configuration
        config_manager = ConfigManager()
        api_key = config_manager.get("api_key")
        
        if not api_key:
            print("Claude API key not configured. Please set CLAUDE_API_KEY environment variable.")
            return 1
        
        # Initialize components
        git_interface = GitCLI()
        ai_reviewer = ClaudeAIReviewer(api_key)
        
        # Choose UI based on availability
        if GUI_TOOLKIT == "PyQt5":
            ui = PyQtUI()
        else:
            ui = TerminalUI()
            print("Using terminal-based UI as PyQt5 is not available.")
        
        # Run the reviewer
        reviewer = PRReviewer(git_interface, ai_reviewer, ui)
        return reviewer.run()
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())