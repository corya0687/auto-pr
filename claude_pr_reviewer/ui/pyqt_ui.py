"""
PyQt5-based UI implementation.
"""

from typing import Dict, Any, List

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QTabWidget, 
                              QTextEdit, QMessageBox, QSplitter, QGridLayout,
                              QTextBrowser, QScrollArea)
    from PyQt5.QtCore import Qt, QRegExp
    from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor
    
    from claude_pr_reviewer.interfaces import UserInterfaceInterface
    from claude_pr_reviewer.ai import DiffSyntaxHighlighter
    
    class PyQtUI(UserInterfaceInterface):
        """Concrete implementation of UserInterfaceInterface using PyQt5"""
        
        def show_review(self, review_data: Dict[str, Any]) -> bool:
            """
            Display the review in a PyQt5 window and 
            return True if user confirms to proceed with push
            """
            from claude_pr_reviewer.ui import GUI_TOOLKIT
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
            from claude_pr_reviewer.ui import GUI_TOOLKIT
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
except ImportError:
    # Define a dummy class for when PyQt5 is not available
    class PyQtUI:
        """Dummy PyQtUI class when PyQt5 is not available"""
        def __init__(self, *args, **kwargs):
            pass