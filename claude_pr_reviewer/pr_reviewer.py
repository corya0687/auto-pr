"""
PR Reviewer - The main class that coordinates the PR review process.
"""

from typing import Dict, Any
from claude_pr_reviewer.interfaces import GitInterface, AIReviewerInterface, UserInterfaceInterface


class PRReviewer:
    """Main class that coordinates the PR review process"""
    
    def __init__(
        self,
        git_interface: GitInterface,
        ai_reviewer: AIReviewerInterface,
        ui: UserInterfaceInterface
    ):
        """Initialize with required components"""
        self.git = git_interface
        self.ai_reviewer = ai_reviewer
        self.ui = ui
    
    def run(self) -> int:
        """Run the PR review process, return exit code (0 for success)"""
        try:
            # Get the diff and related info
            diff = self.git.get_diff()
            if not diff.strip():
                print("No changes to review. Proceeding with push.")
                return 0  # No changes to review
            
            commit_msg = self.git.get_commit_message()
            branch_name = self.git.get_branch_name()
            
            # Get AI review
            review_data = self.ai_reviewer.review_code(diff, commit_msg, branch_name)
            
            if "error" in review_data:
                self.ui.show_error(f"Error during review: {review_data['error']}")
                return 1
            
            # Show review to user and get decision
            proceed = self.ui.show_review(review_data)
            
            if proceed:
                print("User chose to proceed with push.")
                return 0  # Exit code 0 allows the push to continue
            else:
                print("Push cancelled by user.")
                return 1  # Exit code 1 stops the push
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(error_msg)
            self.ui.show_error(error_msg)
            return 1