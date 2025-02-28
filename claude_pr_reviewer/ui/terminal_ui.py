"""
Terminal-based UI implementation.
"""

from typing import Dict, Any
from claude_pr_reviewer.interfaces import UserInterfaceInterface


class TerminalUI(UserInterfaceInterface):
    """Fallback terminal-based UI implementation"""
    
    def show_review(self, review_data: Dict[str, Any]) -> bool:
        """Display the review in the terminal and get user confirmation"""
        print("\n\n===== CLAUDE PR REVIEW =====")
        print("\nReview Results:")
        print(review_data.get("review_text", "No review available."))
        
        if review_data.get("issues"):
            print("\nIssues:")
            for issue in review_data["issues"]:
                print(f"• {issue}")
        
        if review_data.get("suggestions"):
            print("\nSuggestions:")
            for suggestion in review_data["suggestions"]:
                print(f"• {suggestion}")
        
        has_critical = any("critical" in str(issue).lower() for issue in review_data.get("issues", []))
        if has_critical:
            print("\n⚠️  CRITICAL ISSUES FOUND! Please fix before pushing.")
            
        while True:
            response = input("\nDo you want to proceed with the push? (y/n): ").lower()
            if response in ('y', 'yes'):
                return True
            elif response in ('n', 'no'):
                return False
            else:
                print("Please enter 'y' or 'n'")
    
    def show_error(self, message: str) -> None:
        """Display an error message in the terminal"""
        print(f"\nERROR: {message}")