"""
Interface for user interaction.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class UserInterfaceInterface(ABC):
    """Interface for user interaction"""
    
    @abstractmethod
    def show_review(self, review_data: Dict[str, Any]) -> bool:
        """Display the review and get user confirmation to proceed"""
        pass
    
    @abstractmethod
    def show_error(self, message: str) -> None:
        """Display an error message"""
        pass