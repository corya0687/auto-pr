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
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QTabWidget, 
                               QTextEdit, QMessageBox, QSplitter, QGridLayout,
                               QTextBrowser, QScrollArea)
    from PyQt5.QtCore import Qt, QRegExp
    from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor
    GUI_TOOLKIT = "PyQt5"
except ImportError:
    # Fallback to terminal-based UI if PyQt5 is not available
    GUI_TOOLKIT = "Terminal"


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

# Syntax highlighter for code diffs
class DiffSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for git diff output"""
    
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []
        
        # Added lines (green)
        added_format = QTextCharFormat()
        added_format.setBackground(QColor(204, 255, 204))  # Light green
        added_format.setForeground(QColor(0, 100, 0))      # Dark green
        self.highlighting_rules.append((QRegExp("^\\+.*"), added_format))
        
        # Removed lines (red)
        removed_format = QTextCharFormat()
        removed_format.setBackground(QColor(255, 204, 204))  # Light red
        removed_format.setForeground(QColor(139, 0, 0))      # Dark red
        self.highlighting_rules.append((QRegExp("^-.*"), removed_format))
        
        # Header lines (blue)
        header_format = QTextCharFormat()
        header_format.setForeground(QColor(0, 0, 139))  # Dark blue
        header_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegExp("^@@.*@@"), header_format))
        
        # File paths (purple)
        file_format = QTextCharFormat()
        file_format.setForeground(QColor(128, 0, 128))  # Purple
        file_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegExp("^diff --git.*|^---.*|^\\+\\+\\+.*"), file_format))
        
        # Chunk headers
        chunk_format = QTextCharFormat()
        chunk_format.setBackground(QColor(232, 232, 255))  # Light lavender
        chunk_format.setForeground(QColor(70, 70, 70))     # Dark gray
        self.highlighting_rules.append((QRegExp("^@@ .*"), chunk_format))

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            if index >= 0:
                length = expression.matchedLength()
                self.setFormat(0, length, format)

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
        # Check if there's anything to review
        if not diff.strip():
            return {
                "review_text": "No changes to review.",
                "suggestions": [],
                "issues": [],
                "raw_response": {},
                "diff": ""
            }
            
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
            
            # Ensure we have valid content to work with
            review_text = ""
            if "content" in result and len(result["content"]) > 0 and "text" in result["content"][0]:
                review_text = result["content"][0]["text"]
            else:
                review_text = "Could not extract review text from API response."
                
            return {
                "review_text": review_text,
                "suggestions": self._extract_suggestions(review_text),
                "issues": self._extract_issues(review_text),
                "raw_response": result,
                "diff": diff  # Include the diff for side-by-side view
            }
        except requests.RequestException as e:
            return {
                "error": str(e),
                "review_text": f"Error calling Claude API: {e}",
                "suggestions": [],
                "issues": [],
                "diff": diff,  # Include the diff even on error
                "raw_response": {}
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
        if not review_text:
            return []
            
        suggestions = []
        in_suggestions_section = False
        
        try:
            for line in review_text.split('\n'):
                # Check for section headers in various formats
                if 'suggestion' in line.lower() or 'improvement' in line.lower():
                    in_suggestions_section = True
                    continue
                elif in_suggestions_section and (line.startswith('- ') or line.startswith('* ')):
                    suggestions.append(line[2:].strip())
                elif in_suggestions_section and (line.startswith('#') or line == '' or 
                                               'issue' in line.lower() or 
                                               'question' in line.lower() or
                                               'summary' in line.lower()):
                    in_suggestions_section = False
            
            # If we didn't find any formatted suggestions, look for any lines with suggestion-like content
            if not suggestions:
                for line in review_text.split('\n'):
                    if ('suggest' in line.lower() or 'could' in line.lower() or 'would be better' in line.lower()) and len(line) > 10:
                        suggestions.append(line.strip())
                        
            return suggestions[:10]  # Limit to 10 suggestions
        except Exception:
            return []
    
    def _extract_issues(self, review_text: str) -> List[str]:
        """Extract issues from the review text"""
        if not review_text:
            return []
            
        issues = []
        in_issues_section = False
        
        try:
            for line in review_text.split('\n'):
                # Check for section headers in various formats
                if 'issue' in line.lower() or 'problem' in line.lower() or 'bug' in line.lower():
                    in_issues_section = True
                    continue
                elif in_issues_section and (line.startswith('- ') or line.startswith('* ')):
                    issues.append(line[2:].strip())
                elif in_issues_section and (line.startswith('#') or line == '' or
                                          'suggestion' in line.lower() or
                                          'question' in line.lower() or
                                          'summary' in line.lower()):
                    in_issues_section = False
            
            # If we didn't find any formatted issues, look for any lines with issue-like content
            if not issues:
                for line in review_text.split('\n'):
                    if ('issue' in line.lower() or 'bug' in line.lower() or 'error' in line.lower() or 'fix' in line.lower()) and len(line) > 10:
                        issues.append(line.strip())
            
            # Also check for critical issues at the beginning
            if review_text and "CRITICAL ISSUES FOUND" in review_text[:100]:
                issues.insert(0, "CRITICAL ISSUES FOUND - Please fix before committing")
                
            return issues[:10]  # Limit to 10 issues
        except Exception:
            return []


class PyQtUI(UserInterfaceInterface):
    """Concrete implementation of UserInterfaceInterface using PyQt5"""
    
    def show_review(self, review_data: Dict[str, Any]) -> bool:
        """
        Display the review in a PyQt5 window and 
        return True if user confirms to proceed with push
        """
        if GUI_TOOLKIT != "PyQt5":
            return self._fallback_show_review(review_data)
            
        self.user_decision = False
        
        # Validate review_data has all required fields
        if not isinstance(review_data, dict):
            review_data = {
                "review_text": "Error: Invalid review data received",
                "suggestions": [],
                "issues": [],
                "raw_response": {}
            }
            
        # Ensure all expected keys exist with default values if missing
        if "review_text" not in review_data:
            review_data["review_text"] = "No review text available."
        if "suggestions" not in review_data:
            review_data["suggestions"] = []
        if "issues" not in review_data:
            review_data["issues"] = []
        if "raw_response" not in review_data:
            review_data["raw_response"] = {}
            
        # Extract diff from raw response if available
        diff_text = ""
        if "raw_response" in review_data and "diff" in review_data:
            diff_text = review_data["diff"]
        
        # Create Qt application
        app = QApplication.instance() or QApplication([])
        
        # Create main window
        try:
            # Main window with custom styling
            self.window = QMainWindow()
            self.window.setWindowTitle("Claude PR Review")
            self.window.resize(1200, 800)
            self.window.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                }
                QTabWidget::pane {
                    border: 1px solid #cccccc;
                    background-color: white;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #333333;
                    border: 1px solid #cccccc;
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    padding: 6px 12px;
                    min-width: 80px;
                }
                QTabBar::tab:selected {
                    background-color: white;
                    border-bottom: 1px solid white;
                }
                QTextEdit, QTextBrowser {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                    color: #333333;
                    font-family: 'Consolas', 'Monaco', monospace;
                }
                QPushButton {
                    background-color: #4b7bec;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3867d6;
                }
                QPushButton#cancel {
                    background-color: #fc5c65;
                }
                QPushButton#cancel:hover {
                    background-color: #eb3b5a;
                }
            """)
            
            # Central widget and main layout
            central_widget = QWidget()
            self.window.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setSpacing(15)
            
            # Title label
            title_label = QLabel("Claude AI PR Review")
            title_font = QFont()
            title_font.setPointSize(18)
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("color: #2c3e50; margin-bottom: 15px;")
            main_layout.addWidget(title_label)
            
            # Main content area with tabs
            tab_widget = QTabWidget()
            main_layout.addWidget(tab_widget)
            
            # Code Review tab with side-by-side view
            if diff_text:
                diff_tab = QWidget()
                diff_layout = QVBoxLayout(diff_tab)
                
                # Split view for code and comments
                splitter = QSplitter(Qt.Horizontal)
                
                # Create a single content area with inline comments
                diff_browser = QTextBrowser()
                diff_browser.setOpenExternalLinks(True)
                diff_browser.setLineWrapMode(QTextEdit.NoWrap)
                
                # Set monospace font for code
                code_font = QFont("Courier New", 10)
                diff_browser.setFont(code_font)
                
                # Process the diff and add inline comments
                # First get the overall review summary
                review_summary = review_data.get("review_text", "").replace('\n', '<br>')
                
                # Extract issues and suggestions
                issues = review_data.get("issues", [])
                suggestions = review_data.get("suggestions", [])
                
                # Process the diff to add inline comments
                diff_lines = diff_text.splitlines()
                processed_diff = []
                file_path = ""
                current_section = ""
                
                # Summary header at the top
                processed_diff.append("""
                <div style="background-color: #f8f9fa; border: 1px solid #ddd; padding: 10px; margin-bottom: 20px; border-radius: 5px;">
                    <h3 style="color: #2c3e50; margin-top: 0;">Review Summary</h3>
                    <div style="color: #34495e;">""" + review_summary + """</div>
                </div>
                """)
                
                processed_diff.append("<pre>")  # Start preformatted text
                
                for i, line in enumerate(diff_lines):
                    # Colorize diff lines based on content
                    styled_line = line
                    
                    # File headers (diff --git, +++ or ---)
                    if line.startswith("diff --git") or line.startswith("+++") or line.startswith("---"):
                        if line.startswith("diff --git"):
                            # Extract file path
                            parts = line.split(" ")
                            if len(parts) > 2:
                                file_path = parts[2][2:]  # Remove a/ prefix
                        
                        styled_line = '<span style="color: #8e44ad; font-weight: bold;">' + line + '</span>'
                    
                    # Chunk headers (@@ -x,y +a,b @@)
                    elif line.startswith("@@"):
                        styled_line = '<span style="color: #3498db; background-color: #eef6fc;">' + line + '</span>'
                        
                        # Add a horizontal rule after chunk headers
                        styled_line += '<hr style="border: 0; height: 1px; background-color: #eee; margin: 5px 0;">'
                        
                        # Extract section info if available
                        section_match = line.split("@@")
                        if len(section_match) > 2:
                            current_section = section_match[2].strip()
                    
                    # Added lines
                    elif line.startswith("+"):
                        styled_line = '<span style="color: #27ae60; background-color: #e6ffec;">' + line + '</span>'
                    
                    # Removed lines
                    elif line.startswith("-"):
                        styled_line = '<span style="color: #c0392b; background-color: #ffebe9;">' + line + '</span>'
                    
                    # Context lines
                    else:
                        styled_line = '<span style="color: #34495e;">' + line + '</span>'
                    
                    processed_diff.append(styled_line)
                    
                    # Insert comments after file headers
                    if line.startswith("diff --git") and (issues or suggestions):
                        # Add inline comment for file
                        file_comments = []
                        
                        if issues:
                            # Find issues that might be related to this file
                            file_issues = [issue for issue in issues 
                                         if file_path and (file_path.lower() in issue.lower() or 
                                                        any(keyword in issue.lower() for keyword in current_section.lower().split()))]
                            
                            # If we found specific issues for this file, add them
                            if file_issues:
                                file_comments.append("""
                                <div>
                                    <h4 style="color: #c0392b; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">Issues:</h4>
                                    <ul style="color: #333333; margin-top: 10px; list-style-position: outside; padding-left: 20px;">
                                """)
                                for issue in file_issues:
                                    file_comments.append('<li style="margin-bottom: 10px;">' + issue + '</li>')
                                file_comments.append('</ul></div>')
                        
                        if suggestions:
                            # Find suggestions that might be related to this file
                            file_suggestions = [suggestion for suggestion in suggestions 
                                              if file_path and (file_path.lower() in suggestion.lower() or 
                                                             any(keyword in suggestion.lower() for keyword in current_section.lower().split()))]
                            
                            # If we found specific suggestions for this file, add them
                            if file_suggestions:
                                file_comments.append("""
                                <div style="margin-top: 15px;">
                                    <h4 style="color: #2980b9; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">Suggestions:</h4>
                                    <ul style="color: #333333; margin-top: 10px; list-style-position: outside; padding-left: 20px;">
                                """)
                                for suggestion in file_suggestions:
                                    file_comments.append('<li style="margin-bottom: 10px;">' + suggestion + '</li>')
                                file_comments.append('</ul></div>')
                        
                        # Only add the comment box if we have relevant comments
                        if file_comments:
                            processed_diff.append("</pre>")  # End preformatted text for code
                            processed_diff.append("""
                            <div style="border-left: 4px solid #3498db; background-color: #f8f9fa; 
                                        padding: 15px; margin: 20px 0; border-radius: 0 5px 5px 0;
                                        font-family: Arial, sans-serif; font-size: 14px; color: #333333;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            """)
                            processed_diff.extend(file_comments)
                            processed_diff.append('</div>')
                            processed_diff.append("<pre>")  # Resume preformatted text for code
                    
                    # Add comments after specific interesting chunks of code
                    if line.startswith("@@") and (issues or suggestions):
                        # Identify if any issues or suggestions seem to relate to this chunk
                        chunk_comments = []
                        
                        # Get the next few lines for context
                        context_lines = []
                        for j in range(i+1, min(i+6, len(diff_lines))):
                            if j < len(diff_lines):
                                context_lines.append(diff_lines[j])
                        context_text = ' '.join(context_lines)
                        
                        if issues:
                            # Find issues that might be related to this chunk
                            chunk_issues = [issue for issue in issues 
                                          if any(keyword in issue.lower() for keyword in context_text.lower().split())]
                            
                            # If we found specific issues for this chunk, add them
                            if chunk_issues:
                                chunk_comments.append("""
                                <div>
                                    <h4 style="color: #c0392b; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">Issues in this section:</h4>
                                    <ul style="color: #333333; margin-top: 10px; list-style-position: outside; padding-left: 20px;">
                                """)
                                for issue in chunk_issues:
                                    chunk_comments.append('<li style="margin-bottom: 10px;">' + issue + '</li>')
                                chunk_comments.append('</ul></div>')
                        
                        if suggestions:
                            # Find suggestions that might be related to this chunk
                            chunk_suggestions = [suggestion for suggestion in suggestions 
                                               if any(keyword in suggestion.lower() for keyword in context_text.lower().split())]
                            
                            # If we found specific suggestions for this chunk, add them
                            if chunk_suggestions:
                                chunk_comments.append("""
                                <div style="margin-top: 15px;">
                                    <h4 style="color: #2980b9; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">Suggestions for this section:</h4>
                                    <ul style="color: #333333; margin-top: 10px; list-style-position: outside; padding-left: 20px;">
                                """)
                                for suggestion in chunk_suggestions:
                                    chunk_comments.append('<li style="margin-bottom: 10px;">' + suggestion + '</li>')
                                chunk_comments.append('</ul></div>')
                        
                        # Only add the comment box if we have relevant comments
                        if chunk_comments:
                            processed_diff.append("</pre>")  # End preformatted text for code
                            processed_diff.append("""
                            <div style="border-left: 4px solid #3498db; background-color: #f8f9fa; 
                                        padding: 15px; margin: 20px 0; border-radius: 0 5px 5px 0;
                                        font-family: Arial, sans-serif; font-size: 14px; color: #333333;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            """)
                            processed_diff.extend(chunk_comments)
                            processed_diff.append('</div>')
                            processed_diff.append("<pre>")  # Resume preformatted text for code
                
                processed_diff.append("</pre>")  # End preformatted text
                
                # Add remaining general issues/suggestions at the end
                if issues or suggestions:
                    processed_diff.append("""
                    <div style="background-color: #f8f9fa; border: 1px solid #ddd; padding: 10px; 
                                margin-top: 20px; border-radius: 5px;">
                        <h3 style="color: #2c3e50; margin-top: 0;">Additional Feedback</h3>
                    """)
                    
                    if issues:
                        processed_diff.append("""
                        <h4 style="color: #c0392b; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">Issues (""" + str(len(issues)) + """):</h4>
                        <ul style="color: #333333; margin-top: 10px; list-style-position: outside; padding-left: 20px;">
                        """)
                        for issue in issues:
                            processed_diff.append('<li style="margin-bottom: 12px;">' + issue + '</li>')
                        processed_diff.append("</ul>")
                    
                    if suggestions:
                        processed_diff.append("""
                        <h4 style="color: #2980b9; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">Suggestions (""" + str(len(suggestions)) + """):</h4>
                        <ul style="color: #333333; margin-top: 10px; list-style-position: outside; padding-left: 20px;">
                        """)
                        for suggestion in suggestions:
                            processed_diff.append('<li style="margin-bottom: 12px;">' + suggestion + '</li>')
                        processed_diff.append("</ul>")
                    
                    processed_diff.append("</div>")
                
                # Join all the HTML and set it
                diff_browser.setHtml('\n'.join(processed_diff))
                
                # Add to layout
                diff_layout.addWidget(diff_browser)
                
                tab_widget.addTab(diff_tab, "Code Review")
            
            # Full review tab
            review_tab = QWidget()
            review_layout = QVBoxLayout(review_tab)
            
            # Create text browser for HTML formatting
            review_text_browser = QTextBrowser()
            review_text_browser.setOpenExternalLinks(True)
            
            # Format content with HTML styling
            review_html = """
            <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2 style="color: #2c3e50; border-bottom: 1px solid #ecf0f1; padding-bottom: 10px;">
                    Review Summary
                </h2>
                <div style="color: #34495e; margin-bottom: 20px;">
                    """ + review_data.get("review_text", "No review available.").replace('\n', '<br>') + """
                </div>
            """
            
            # Add issues section if there are issues
            if review_data.get("issues"):
                review_html += """
                <h2 style="color: #c0392b; border-bottom: 1px solid #ecf0f1; padding-bottom: 10px; 
                           margin-top: 30px;">
                    Issues to Address
                </h2>
                <ul style="color: #e74c3c;">
                """
                
                for issue in review_data["issues"]:
                    review_html += '<li style="margin-bottom: 12px;">' + issue + '</li>'
                
                review_html += "</ul>"
            
            # Add suggestions section if there are suggestions
            if review_data.get("suggestions"):
                review_html += """
                <h2 style="color: #2980b9; border-bottom: 1px solid #ecf0f1; padding-bottom: 10px; 
                           margin-top: 30px;">
                    Suggestions for Improvement
                </h2>
                <ul style="color: #3498db;">
                """
                
                for suggestion in review_data["suggestions"]:
                    review_html += '<li style="margin-bottom: 12px;">' + suggestion + '</li>'
                
                review_html += "</ul>"
            
            review_html += "</div>"
            
            review_text_browser.setHtml(review_html)
            review_layout.addWidget(review_text_browser)
            tab_widget.addTab(review_tab, "Summary")
            
            # Debug tab with raw response for troubleshooting
            debug_tab = QWidget()
            debug_layout = QVBoxLayout(debug_tab)
            debug_text = QTextEdit()
            debug_text.setReadOnly(True)
            
            # Show all keys and their types, plus review_text contents
            debug_info = "Review Data Keys:\n"
            for key in review_data:
                debug_info += f"- {key}: {type(review_data[key]).__name__}\n"
                
            debug_info += "\nReview Text Content:\n"
            debug_info += review_data.get("review_text", "No review text")
            
            debug_text.setText(debug_info)
            debug_layout.addWidget(debug_text)
            tab_widget.addTab(debug_tab, "Debug")
            
            # Buttons layout
            buttons_layout = QHBoxLayout()
            main_layout.addLayout(buttons_layout)
            
            # Warning text for critical issues
            has_critical = any("critical" in str(issue).lower() for issue in review_data.get("issues", []))
            if has_critical:
                warning_label = QLabel("⚠️ Critical issues found! Please fix before pushing.")
                warning_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
                buttons_layout.addWidget(warning_label)
                buttons_layout.addStretch(1)
            else:
                buttons_layout.addStretch(1)
            
            # Cancel button
            cancel_btn = QPushButton("Cancel Push")
            cancel_btn.setObjectName("cancel")
            cancel_btn.clicked.connect(lambda: self._on_decision(False))
            buttons_layout.addWidget(cancel_btn)
            
            # Proceed button
            proceed_btn = QPushButton("Proceed Anyway")
            
            # If critical issues exist, require confirmation to proceed
            if has_critical:
                proceed_btn.clicked.connect(self._confirm_proceed)
            else:
                proceed_btn.clicked.connect(lambda: self._on_decision(True))
                
            buttons_layout.addWidget(proceed_btn)
            
            # Show window
            self.window.show()
            
            # Center window on screen
            frameGm = self.window.frameGeometry()
            screen = app.desktop().screenNumber(app.desktop().cursor().pos())
            centerPoint = app.desktop().screenGeometry(screen).center()
            frameGm.moveCenter(centerPoint)
            self.window.move(frameGm.topLeft())
            
            # Run application
            app.exec_()
            
            return self.user_decision
            
        except Exception as e:
            print(f"Error displaying UI: {e}")
            QMessageBox.critical(None, "UI Error", f"Error displaying review: {e}")
            return False
    
    def _confirm_proceed(self):
        """Show confirmation dialog for critical issues"""
        confirm = QMessageBox.warning(
            self.window,
            "Critical Issues",
            "Critical issues were found in your code. Are you sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self._on_decision(True)
    
    def _on_decision(self, proceed: bool) -> None:
        """Handle user decision and close window"""
        self.user_decision = proceed
        self.window.close()
    
    def show_error(self, message: str) -> None:
        """Display an error message using QMessageBox"""
        if GUI_TOOLKIT != "PyQt5":
            print(f"Error: {message}")
            return
            
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Error", message)
    
    def _fallback_show_review(self, review_data: Dict[str, Any]) -> bool:
        """Terminal-based fallback for systems without PyQt5"""
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