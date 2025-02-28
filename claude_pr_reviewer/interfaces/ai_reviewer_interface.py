"""
Interface for AI reviewer operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class AIReviewerInterface(ABC):
    """Interface for AI review operations"""
    
    @abstractmethod
    def review_code(self, diff: str, commit_msg: str, branch: str) -> Dict[str, Any]:
        """Review the code and return the results"""
        pass