"""
Claude PR Reviewer - A git hook application that uses Claude AI to review PRs
and displays comments in a GUI before allowing a push.
"""

from claude_pr_reviewer.interfaces import GitInterface, AIReviewerInterface, UserInterfaceInterface
from claude_pr_reviewer.git import GitCLI
from claude_pr_reviewer.ai import ClaudeAIReviewer, DiffSyntaxHighlighter
from claude_pr_reviewer.ui import PyQtUI, TerminalUI
from .config_manager import ConfigManager 
from .pr_reviewer import PRReviewer

__all__ = [
    'GitInterface', 'AIReviewerInterface', 'UserInterfaceInterface',
    'GitCLI', 'ClaudeAIReviewer', 'DiffSyntaxHighlighter',
    'PyQtUI', 'TerminalUI', 'ConfigManager', 'PRReviewer'
]