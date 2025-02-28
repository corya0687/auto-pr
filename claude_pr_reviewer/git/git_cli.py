"""
Git CLI implementation using subprocess.
"""

import subprocess
from claude_pr_reviewer.interfaces import GitInterface


class GitCLI(GitInterface):
    """Concrete implementation of GitInterface using subprocess"""
    
    def get_diff(self) -> str:
        """Get the diff that would be pushed using git diff command"""
        diff = ""
        
        # Check for staged changes
        try:
            staged_diff = subprocess.check_output(
                ["git", "diff", "--staged"],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            if staged_diff.strip():
                diff += staged_diff
        except subprocess.CalledProcessError:
            pass

        # Only proceed with other checks if we don't have staged changes yet
        if not diff.strip():
            # Check if there's a HEAD reference (at least one commit)
            has_commits = True
            try:
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
            except subprocess.CalledProcessError:
                has_commits = False
            
            # If we have no commits yet, get all changes
            if not has_commits:
                try:
                    # Get all changes
                    return subprocess.check_output(
                        ["git", "diff"],
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
                except subprocess.CalledProcessError:
                    return ""
            
            # If we have commits, try to get the diff between HEAD and the remote tracking branch
            try:
                remote_branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], 
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                ).strip()
                
                branch_diff = subprocess.check_output(
                    ["git", "diff", remote_branch + "..HEAD"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                if branch_diff.strip():
                    diff += branch_diff
            except subprocess.CalledProcessError:
                # If there's no upstream branch, get the diff of all commits that will be pushed
                try:
                    branch_diff = subprocess.check_output(
                        ["git", "diff", "origin/main...HEAD"],
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
                    if branch_diff.strip():
                        diff += branch_diff
                except subprocess.CalledProcessError:
                    # Fallback to just showing the diff of the latest commit
                    try:
                        commit_diff = subprocess.check_output(
                            ["git", "diff", "HEAD~1..HEAD"],
                            stderr=subprocess.STDOUT,
                            universal_newlines=True
                        )
                        if commit_diff.strip():
                            diff += commit_diff
                    except subprocess.CalledProcessError:
                        pass
        
        # Debug output
        if not diff.strip():
            print("No diff detected in any of the tried methods.")
        else:
            print(f"Found diff with {len(diff.splitlines())} lines of changes.")
        
        return diff
    
    def get_commit_message(self) -> str:
        """Get the latest commit message or a placeholder if no commits yet"""
        try:
            return subprocess.check_output(
                ["git", "log", "-1", "--pretty=%B"],
                universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            # No commits yet
            return "Initial commit"
    
    def get_branch_name(self) -> str:
        """Get the current branch name or a placeholder if not on a branch"""
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            return "main"