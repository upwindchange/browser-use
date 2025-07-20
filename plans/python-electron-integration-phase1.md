# Implementation Plan: Phase 1 - Python Core Infrastructure Only

## Overview
I'll implement only the Python-side components for browser-use integration with Autai. This includes ElectronSession and ElectronUIBridge that will communicate with the Electron WebSocket servers you'll implement later.

## Implementation Steps

### 1. Create ElectronSession (`browser-use/browser_use/browser/electron_session.py`)

This will be a drop-in replacement for BrowserSession that:
- Connects to WebSocket server on port 9222 for browser control
- Implements all required BrowserSession methods
- Maintains compatibility with browser-use's existing API
- Key methods to implement:
  - `start()` - Connect to WebSocket
  - `navigate()` - Navigate to URLs
  - `get_current_page()` - Get active page
  - `create_new_tab()` - Create new tabs
  - `switch_tab()` - Switch between tabs
  - `execute_javascript()` - Execute JS in pages
  - `take_screenshot()` - Capture screenshots
  - `get_state_summary()` - Get browser state for agent
  - `is_connected()` - Check connection status

### 2. Create ElectronUIBridge (`browser-use/browser_use/electron/ui_bridge.py`)

This will handle UI communication:
- Connect to WebSocket server on port 9223
- Forward agent events to Electron UI
- Handle user input requests (human-in-the-loop)
- Key features:
  - Event forwarding from agent to UI
  - User input request/response handling
  - Notification sending
  - Command handling (pause/resume/stop)

### 3. Create Custom Actions (`browser-use/browser_use/electron/actions.py`)

Human-in-the-loop actions for the agent:
- `ask_user_electron` - Request text input from user
- `confirm_action_electron` - Get user confirmation
- `select_option_electron` - Let user choose from options
- `notify_user_electron` - Send notifications to user

### 4. Update browser-use initialization (`browser-use/browser_use/browser/__init__.py`)

Modify the import logic to:
- Check for `USE_ELECTRON_BACKEND` environment variable
- Import ElectronSession when enabled
- Maintain backward compatibility with Playwright

## Key Implementation Details

### ElectronSession Design
- Implement ElectronPage class as a proxy for Electron windows
- Use UUID-based request/response pattern for WebSocket commands
- Handle async operations with proper error handling
- Maintain state tracking for windows/tabs

### ElectronUIBridge Design
- Event-driven architecture using asyncio
- Automatic reconnection on connection loss
- Queue-based message handling
- Integration with browser-use's EventBus

### WebSocket Protocol Specifications

#### Browser Control Protocol (Port 9222)
```python
# Request format
{
    "id": "unique-request-id",
    "method": "navigate",
    "params": {"url": "https://example.com", "new_tab": false}
}

# Response format
{
    "id": "unique-request-id",
    "result": {"window_id": "window-123", "url": "https://example.com"}
}
```

#### UI Bridge Protocol (Port 9223)
```python
# Agent event format
{
    "type": "agent_event",
    "event": "CreateAgentStepEvent",
    "data": {...},
    "timestamp": 1234567890
}

# User input request
{
    "type": "input_request",
    "input_id": "input-123",
    "prompt": "Please enter your name",
    "options": ["Yes", "No"]  # Optional
}
```

## Files to Create

1. `browser-use/browser_use/browser/electron_session.py` - Main ElectronSession implementation
2. `browser-use/browser_use/electron/__init__.py` - Package initialization
3. `browser-use/browser_use/electron/ui_bridge.py` - UI Bridge implementation
4. `browser-use/browser_use/electron/actions.py` - Custom actions for human interaction

## Files to Modify

1. `browser-use/browser_use/browser/__init__.py` - Add conditional import logic

This implementation will provide a complete Python-side integration that's ready to connect to the Electron WebSocket servers when you implement them.