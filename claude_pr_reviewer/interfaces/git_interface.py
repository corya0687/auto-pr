"""
Interface for git operations.
"""

from abc import ABC, abstractmethod


class GitInterface(ABC):
    """Interface for git operations"""
    
    @abstractmethod
    def get_diff(self) -> str:
        """Get the diff that would be pushed"""
        pass
    
    @abstractmethod
    def get_commit_message(self) -> str:
        """Get the latest commit message"""
        pass
    
    @abstractmethod
    def get_branch_name(self) -> str:
        """Get the current branch name"""
        pass