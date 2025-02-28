"""
User interface implementation classes.
"""

try:
    from .pyqt_ui import PyQtUI
    GUI_TOOLKIT = "PyQt5"
except ImportError:
    # PyQt5 not available
    GUI_TOOLKIT = "Terminal"

from .terminal_ui import TerminalUI

__all__ = ['PyQtUI', 'TerminalUI', 'GUI_TOOLKIT']