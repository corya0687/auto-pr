#!/usr/bin/env python3
"""
Claude PR Reviewer - A git hook application that uses Claude AI to review PRs
and displays comments in a GUI before allowing a push.
"""

import os
import sys
import json
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple

import requests
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk


# --- Interfaces ---

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


class AIReviewerInterface(ABC):
    """Interface for AI review operations"""
    
    @abstractmethod
    def review_code(self, diff: str, commit_msg: str, branch: str) -> Dict[str, Any]:
        """Review the code and return the results"""
        pass


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


# --- Concrete Implementations ---

class GitCLI(GitInterface):
    """Concrete implementation of GitInterface using subprocess"""
    
    def get_diff(self) -> str:
        """Get the diff that would be pushed using git diff command"""
        # Get the diff between HEAD and the remote tracking branch
        try:
            remote_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], 
                stderr=subprocess.STDOUT,
                universal_newlines=True
            ).strip()
            
            diff = subprocess.check_output(
                ["git", "diff", remote_branch + "..HEAD"],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            return diff
        except subprocess.CalledProcessError:
            # If there's no upstream branch, get the diff of all commits that will be pushed
            try:
                diff = subprocess.check_output(
                    ["git", "diff", "origin/main...HEAD"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                return diff
            except subprocess.CalledProcessError:
                # Fallback to just showing the diff of the latest commit
                return subprocess.check_output(
                    ["git", "diff", "HEAD~1..HEAD"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
    
    def get_commit_message(self) -> str:
        """Get the latest commit message"""
        return subprocess.check_output(
            ["git", "log", "-1", "--pretty=%B"],
            universal_newlines=True
        ).strip()
    
    def get_branch_name(self) -> str:
        """Get the current branch name"""
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            universal_newlines=True
        ).strip()


class ClaudeAIReviewer(AIReviewerInterface):
    """Concrete implementation of AIReviewerInterface using Claude API"""
    
    def __init__(self, api_key: str):
        """Initialize with Claude API key"""
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def review_code(self, diff: str, commit_msg: str, branch: str) -> Dict[str, Any]:
        """Review the code using Claude AI and return the results"""
        prompt = self._create_prompt(diff, commit_msg, branch)
        
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                "review_text": result["content"][0]["text"],
                "suggestions": self._extract_suggestions(result["content"][0]["text"]),
                "issues": self._extract_issues(result["content"][0]["text"]),
                "raw_response": result
            }
        except requests.RequestException as e:
            return {
                "error": str(e),
                "review_text": f"Error calling Claude API: {e}",
                "suggestions": [],
                "issues": []
            }
    
    def _create_prompt(self, diff: str, commit_msg: str, branch: str) -> str:
        """Create the prompt for Claude"""
        return f"""Please review the following git diff for a commit on branch "{branch}" with commit message: "{commit_msg}".

Focus on:
1. Potential bugs or issues
2. Security concerns
3. Code quality and maintainability
4. Suggestions for improvement

Format your response with these sections:
- Summary: Brief overview of the changes
- Issues: List any problems that should be fixed (prioritized)
- Suggestions: Optional improvements that would be nice to have
- Questions: Anything that needs clarification

Here's the diff:
```
{diff}
```

Please be concise and focus on the most important points. If you find critical issues that should block the commit, start your response with "CRITICAL ISSUES FOUND".
"""
    
    def _extract_suggestions(self, review_text: str) -> List[str]:
        """Extract suggestions from the review text"""
        suggestions = []
        in_suggestions_section = False
        
        for line in review_text.split('\n'):
            if line.lower().startswith('suggestion') or line.lower().startswith('- suggestion'):
                in_suggestions_section = True
                continue
            elif in_suggestions_section and line.startswith('- '):
                suggestions.append(line[2:])
            elif in_suggestions_section and (line.startswith('#') or line == '' or line.lower().startswith('question')):
                in_suggestions_section = False
        
        return suggestions
    
    def _extract_issues(self, review_text: str) -> List[str]:
        """Extract issues from the review text"""
        issues = []
        in_issues_section = False
        
        for line in review_text.split('\n'):
            if line.lower().startswith('issue') or line.lower().startswith('- issue'):
                in_issues_section = True
                continue
            elif in_issues_section and line.startswith('- '):
                issues.append(line[2:])
            elif in_issues_section and (line.startswith('#') or line == '' or line.lower().startswith('suggestion')):
                in_issues_section = False
        
        # Also check for critical issues at the beginning
        if "CRITICAL ISSUES FOUND" in review_text[:100]:
            issues.insert(0, "CRITICAL ISSUES FOUND - Please fix before committing")
            
        return issues


class TkinterUI(UserInterfaceInterface):
    """Concrete implementation of UserInterfaceInterface using Tkinter"""
    
    def show_review(self, review_data: Dict[str, Any]) -> bool:
        """
        Display the review in a Tkinter window and 
        return True if user confirms to proceed with push
        """
        self.user_decision = False
        
        # Create main window
        root = tk.Tk()
        root.title("Claude PR Review")
        root.geometry("800x600")
        
        # Create and configure main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(
            main_frame, 
            text="Claude AI PR Review Results", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Create notebook for tabbed interface
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Full review tab
        review_tab = ttk.Frame(notebook)
        notebook.add(review_tab, text="Full Review")
        
        review_text = scrolledtext.ScrolledText(
            review_tab, 
            wrap=tk.WORD, 
            width=80, 
            height=20,
            font=("Consolas", 11)
        )
        review_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        review_text.insert(tk.END, review_data["review_text"])
        review_text.config(state=tk.DISABLED)
        
        # Issues tab
        if review_data.get("issues"):
            issues_tab = ttk.Frame(notebook)
            notebook.add(issues_tab, text=f"Issues ({len(review_data['issues'])})")
            
            issues_text = scrolledtext.ScrolledText(
                issues_tab, 
                wrap=tk.WORD, 
                width=80, 
                height=20,
                font=("Consolas", 11)
            )
            issues_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            for issue in review_data["issues"]:
                issues_text.insert(tk.END, f"• {issue}\n\n")
            
            issues_text.config(state=tk.DISABLED)
        
        # Suggestions tab
        if review_data.get("suggestions"):
            suggestions_tab = ttk.Frame(notebook)
            notebook.add(suggestions_tab, text=f"Suggestions ({len(review_data['suggestions'])})")
            
            suggestions_text = scrolledtext.ScrolledText(
                suggestions_tab, 
                wrap=tk.WORD, 
                width=80, 
                height=20,
                font=("Consolas", 11)
            )
            suggestions_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            for suggestion in review_data["suggestions"]:
                suggestions_text.insert(tk.END, f"• {suggestion}\n\n")
            
            suggestions_text.config(state=tk.DISABLED)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        # Warning text
        has_critical = any("critical" in issue.lower() for issue in review_data.get("issues", []))
        if has_critical:
            warning_label = ttk.Label(
                buttons_frame,
                text="⚠️ Critical issues found! Please fix before pushing.",
                foreground="red",
                font=("Arial", 12, "bold")
            )
            warning_label.pack(side=tk.LEFT, padx=5)
        
        # Cancel button
        cancel_btn = ttk.Button(
            buttons_frame, 
            text="Cancel Push", 
            command=lambda: self._on_decision(root, False)
        )
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        # Proceed button
        proceed_btn = ttk.Button(
            buttons_frame, 
            text="Proceed Anyway", 
            command=lambda: self._on_decision(root, True)
        )
        proceed_btn.pack(side=tk.RIGHT, padx=5)
        
        # If critical issues exist, require confirmation to proceed
        if has_critical:
            def confirm_proceed():
                if messagebox.askyesno(
                    "Critical Issues",
                    "Critical issues were found in your code. Are you sure you want to proceed?",
                    icon=messagebox.WARNING
                ):
                    self._on_decision(root, True)
            
            proceed_btn.config(command=confirm_proceed)
        
        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'+{x}+{y}')
        
        # Set window to be on top
        root.attributes('-topmost', True)
        root.update()
        root.attributes('-topmost', False)
        
        # Set initial focus to notebook
        notebook.focus_set()
        
        # Start the main event loop
        root.mainloop()
        
        return self.user_decision
    
    def _on_decision(self, root: tk.Tk, proceed: bool) -> None:
        """Handle user decision and close window"""
        self.user_decision = proceed
        root.destroy()
    
    def show_error(self, message: str) -> None:
        """Display an error message using messagebox"""
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror("Error", message)
        root.destroy()


class ConfigManager:
    """Class to manage configuration"""
    
    def __init__(self, config_path: str = "~/.claude_pr_reviewer.json"):
        """Initialize with config file path"""
        self.config_path = os.path.expanduser(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                return self._create_default_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        config = {
            "api_key": "",
            "model": "claude-3-haiku-20240307",
            "max_diff_size": 10000,  # Max characters to send to Claude
        }
        
        # Prompt for API key if not in environment
        api_key = os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            print("Claude API key not found.")
            api_key = input("Please enter your Claude API key: ").strip()
        
        config["api_key"] = api_key
        
        # Save the config
        self._save_config(config)
        return config
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str) -> Any:
        """Get configuration value"""
        return self.config.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.config[key] = value
        self._save_config(self.config)


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
            
            return 0 if proceed else 1
            
        except Exception as e:
            self.ui.show_error(f"Unexpected error: {str(e)}")
            return 1


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
        ui = TkinterUI()
        
        # Run the reviewer
        reviewer = PRReviewer(git_interface, ai_reviewer, ui)
        return reviewer.run()
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())