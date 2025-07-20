# Browser-Use Electron Integration

This document explains how to use browser-use with the Electron backend (Autai) instead of Playwright.

## Overview

The Electron integration allows browser-use to control an Electron-based browser (Autai) through WebSocket connections, enabling:

- Full browser control without Playwright
- Human-in-the-loop interactions
- Real-time UI updates
- Better integration with desktop applications

## Architecture

The integration uses two WebSocket connections:

1. **Browser Control (Port 9222)**: Handles browser operations (navigation, clicks, typing)
2. **UI Bridge (Port 9223)**: Handles UI events and human interactions

## Setup

### 1. Enable Electron Backend

Set the environment variable:

```bash
export USE_ELECTRON_BACKEND=true
```

Or in Python:

```python
import os
os.environ['USE_ELECTRON_BACKEND'] = 'true'
```

### 2. Start Autai Electron App

Ensure the Autai Electron application is running with WebSocket servers enabled on ports 9222 and 9223.

### 3. Use Browser-Use Normally

Once enabled, `BrowserSession` will automatically use `ElectronSession`:

```python
from browser_use import Agent
from browser_use.llm.openai import ChatOpenAI

agent = Agent(
    task="Search for Python tutorials",
    llm=ChatOpenAI(model="gpt-4")
)
result = await agent.run()
```

## Human-in-the-Loop Features

### Setup UI Bridge

```python
from browser_use.electron import ElectronUIBridge
from browser_use.electron import actions

# Initialize UI bridge
ui_bridge = ElectronUIBridge()
await ui_bridge.connect()

# Set up actions
actions.ui_bridge = ui_bridge
```

### Register Custom Actions

```python
from browser_use.controller import Controller

controller = Controller()

# Register human interaction actions
controller.action("Ask user for input")(actions.ask_user_electron)
controller.action("Confirm action")(actions.confirm_action_electron)
controller.action("Let user select option")(actions.select_option_electron)
controller.action("Notify user")(actions.notify_user_electron)
```

### Subscribe to Agent Events

```python
# Forward agent events to UI
ui_bridge.subscribe_to_agent_events(agent)
```

### Handle UI Commands

```python
# Handle pause/resume/stop from UI
ui_bridge.event_bus.on('ui_command_pause', handle_pause)
ui_bridge.event_bus.on('ui_command_resume', handle_resume)
ui_bridge.event_bus.on('ui_command_stop', handle_stop)
```

## Testing

Run the test script to verify connections:

```bash
python test_electron_connection.py
```

This will test:
- Browser control connection
- UI bridge connection
- Basic operations (navigation, screenshot)
- User input dialogs

## API Compatibility

ElectronSession implements the same API as BrowserSession, including:

- `start()` / `stop()`
- `navigate(url)`
- `get_current_page()`
- `create_new_tab()`
- `switch_tab()`
- `execute_javascript()`
- `take_screenshot()`
- `get_state_summary()`

## WebSocket Protocol

### Browser Control (Port 9222)

Request:
```json
{
    "id": "unique-id",
    "method": "navigate",
    "params": {"url": "https://example.com"}
}
```

Response:
```json
{
    "id": "unique-id",
    "result": {"window_id": "win-123", "url": "https://example.com"}
}
```

### UI Bridge (Port 9223)

Agent Event:
```json
{
    "type": "agent_event",
    "event": "CreateAgentStepEvent",
    "data": {...},
    "timestamp": 1234567890
}
```

User Input Request:
```json
{
    "type": "input_request",
    "input_id": "input-123",
    "prompt": "Please select an option",
    "options": ["Yes", "No"]
}
```

## Troubleshooting

### Connection Failed

1. Check if Autai is running
2. Verify ports 9222 and 9223 are not blocked
3. Check firewall settings

### ElectronSession Not Found

Ensure `USE_ELECTRON_BACKEND=true` is set before importing browser_use modules.

### UI Not Responding

1. Check UI bridge connection
2. Verify event subscriptions are active
3. Check Electron app console for errors

## Example

See `examples/electron_integration_example.py` for a complete working example.