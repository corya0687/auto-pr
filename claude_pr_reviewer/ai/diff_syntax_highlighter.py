"""
Syntax highlighter for git diff output.
"""

try:
    from PyQt5.QtCore import QRegExp
    from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter
    
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
            header_format.setFontWeight(2)  # Bold equivalent in QFont
            self.highlighting_rules.append((QRegExp("^@@.*@@"), header_format))
            
            # File paths (purple)
            file_format = QTextCharFormat()
            file_format.setForeground(QColor(128, 0, 128))  # Purple
            file_format.setFontWeight(2)  # Bold equivalent in QFont
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
except ImportError:
    # Define a dummy class for when PyQt5 is not available
    class DiffSyntaxHighlighter:
        """Dummy syntax highlighter when PyQt5 is not available"""
        def __init__(self, *args, **kwargs):
            pass