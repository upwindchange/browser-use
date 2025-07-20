"""
Electron integration for browser-use.

This module provides integration with Electron-based browsers through WebSocket communication.
"""

from .ui_bridge import ElectronUIBridge

__all__ = ['ElectronUIBridge']