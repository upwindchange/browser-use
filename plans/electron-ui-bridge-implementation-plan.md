# UI Bridge Implementation Plan

## Overview
This document outlines the implementation plan for creating a UI bridge between the browser-use Python library and an Electron application. The architecture uses WebSocket connections to enable bidirectional communication for both browser control and UI updates.

## Architecture Overview

```
┌─────────────────┐     WebSocket       ┌──────────────────┐
│                 │     (port 9222)     │                  │
│  Python Agent   ├────────────────────►│  Electron App    │
│  (Browser       │                     │  (Browser        │
│   Control)      │◄────────────────────┤   Control)       │
│                 │                     │                  │
└────────┬────────┘                     └────────┬─────────┘
         │                                       │
         │ Events                         Updates│
         ▼                                       ▼
┌─────────────────┐     WebSocket       ┌──────────────────┐
│                 │     (port 9223)     │                  │
│  UI Bridge      ├────────────────────►│  Electron UI     │
│  (Event         │                     │  (Display &      │
│   Forwarding)   │◄────────────────────┤   Input)         │
│                 │     User Input      │                  │
└─────────────────┘                     └──────────────────┘
```

## Part 1: Browser-Use Library Implementation

### 1.1 Core UI Bridge Module

**File**: `browser_use/electron/ui_bridge.py`

```python
import asyncio
import json
import logging
from typing import Callable, Dict, Any
from uuid import uuid4
import websockets
from websockets.client import WebSocketClientProtocol
from bubus import EventBus

logger = logging.getLogger(__name__)

class ElectronUIBridge:
    """Bridges browser-use events to Electron UI via WebSocket"""
    
    def __init__(self, ws_url: str = "ws://localhost:9223"):
        self.ws_url = ws_url
        self.ws: WebSocketClientProtocol | None = None
        self.event_bus = EventBus(name="ElectronUIBridge")
        self._input_handlers: Dict[str, Callable] = {}
        self._connected = False
        
    async def connect(self):
        """Establish WebSocket connection to Electron UI"""
        try:
            self.ws = await websockets.connect(self.ws_url)
            self._connected = True
            logger.info(f"Connected to Electron UI at {self.ws_url}")
            asyncio.create_task(self._handle_ui_messages())
        except Exception as e:
            logger.error(f"Failed to connect to Electron UI: {e}")
            raise
            
    async def disconnect(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()
            self._connected = False
            
    async def _handle_ui_messages(self):
        """Handle incoming messages from Electron UI"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self._process_ui_message(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info("UI WebSocket connection closed")
            self._connected = False
        except Exception as e:
            logger.error(f"Error handling UI message: {e}")
            
    async def _process_ui_message(self, data: Dict[str, Any]):
        """Process different types of UI messages"""
        msg_type = data.get('type')
        
        if msg_type == 'user_input':
            # Handle user input response
            input_id = data.get('input_id')
            if handler := self._input_handlers.pop(input_id, None):
                handler(data.get('value'))
                
        elif msg_type == 'command':
            # Handle UI commands (pause, resume, stop)
            command = data.get('command')
            params = data.get('params', {})
            await self.event_bus.emit(f"ui_command_{command}", params)
            
    def subscribe_to_agent_events(self, agent):
        """Subscribe to agent events and forward to UI"""
        
        async def forward_event(event_name: str, event_data: Any):
            if self._connected and self.ws:
                try:
                    # Convert event data to serializable format
                    if hasattr(event_data, 'model_dump'):
                        event_data = event_data.model_dump()
                    elif hasattr(event_data, '__dict__'):
                        event_data = event_data.__dict__
                        
                    await self.ws.send(json.dumps({
                        'type': 'agent_event',
                        'event': event_name,
                        'data': event_data,
                        'timestamp': asyncio.get_event_loop().time()
                    }))
                except Exception as e:
                    logger.error(f"Failed to forward event {event_name}: {e}")
        
        # Subscribe to key agent events
        events_to_forward = [
            'CreateAgentSessionEvent',
            'CreateAgentTaskEvent', 
            'CreateAgentStepEvent',
            'UpdateAgentTaskEvent',
            'CreateAgentOutputFileEvent'
        ]
        
        for event_name in events_to_forward:
            agent.eventbus.on(event_name, lambda evt, name=event_name: 
                             asyncio.create_task(forward_event(name, evt)))
                             
    async def request_user_input(self, prompt: str, options: list[str] | None = None) -> str:
        """Request input from Electron UI (for human-in-the-loop)"""
        if not self._connected or not self.ws:
            raise RuntimeError("Not connected to Electron UI")
            
        input_id = str(uuid4())
        future = asyncio.Future()
        
        # Register handler for response
        self._input_handlers[input_id] = lambda value: future.set_result(value)
        
        # Send input request
        await self.ws.send(json.dumps({
            'type': 'input_request',
            'input_id': input_id,
            'prompt': prompt,
            'options': options
        }))
        
        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=300)  # 5 min timeout
            return result
        except asyncio.TimeoutError:
            self._input_handlers.pop(input_id, None)
            raise TimeoutError("User input request timed out")
            
    async def send_notification(self, title: str, message: str, level: str = 'info'):
        """Send notification to Electron UI"""
        if self._connected and self.ws:
            await self.ws.send(json.dumps({
                'type': 'notification',
                'title': title,
                'message': message,
                'level': level
            }))
```

### 1.2 Custom Action Integration

**File**: `browser_use/electron/actions.py`

```python
from browser_use.controller.registry.views import ActionModel
from browser_use.agent.views import ActionResult
from pydantic import BaseModel, Field

# UI Bridge instance (to be initialized in main code)
ui_bridge = None

class AskUserParams(BaseModel):
    question: str = Field(..., description="Question to ask the user")

async def ask_user_electron(params: AskUserParams) -> ActionResult:
    """Ask user for text input via Electron UI"""
    if not ui_bridge:
        raise RuntimeError("UI Bridge not initialized")
        
    answer = await ui_bridge.request_user_input(params.question)
    return ActionResult(
        extracted_content=f"User answered: {answer}",
        include_in_memory=True
    )

class ConfirmActionParams(BaseModel):
    action: str = Field(..., description="Action to confirm")
    details: str = Field("", description="Additional details about the action")

async def confirm_action_electron(params: ConfirmActionParams) -> ActionResult:
    """Get user confirmation via Electron UI"""
    if not ui_bridge:
        raise RuntimeError("UI Bridge not initialized")
        
    prompt = f"Please confirm: {params.action}"
    if params.details:
        prompt += f"\n\nDetails: {params.details}"
        
    response = await ui_bridge.request_user_input(
        prompt, 
        options=["Yes", "No"]
    )
    
    confirmed = response.lower() == "yes"
    return ActionResult(
        extracted_content=f"User {'confirmed' if confirmed else 'declined'} the action",
        include_in_memory=True
    )

class SelectOptionParams(BaseModel):
    prompt: str = Field(..., description="Prompt for the user")
    options: list[str] = Field(..., description="List of options to choose from")

async def select_option_electron(params: SelectOptionParams) -> ActionResult:
    """Let user select from options via Electron UI"""
    if not ui_bridge:
        raise RuntimeError("UI Bridge not initialized")
        
    selected = await ui_bridge.request_user_input(
        params.prompt,
        options=params.options
    )
    
    return ActionResult(
        extracted_content=f"User selected: {selected}",
        include_in_memory=True
    )

class NotifyUserParams(BaseModel):
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    level: str = Field("info", description="Notification level: info, warning, error")

async def notify_user_electron(params: NotifyUserParams) -> ActionResult:
    """Send notification to user via Electron UI"""
    if not ui_bridge:
        raise RuntimeError("UI Bridge not initialized")
        
    await ui_bridge.send_notification(
        params.title,
        params.message,
        params.level
    )
    
    return ActionResult(
        extracted_content=f"Notified user: {params.title}",
        include_in_memory=False
    )
```

### 1.3 ElectronSession Implementation

**File**: `browser_use/browser/electron_session.py`

```python
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import uuid4
import websockets
from websockets.client import WebSocketClientProtocol

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.views import BrowserStateSummary
from browser_use.browser.types import Page

logger = logging.getLogger(__name__)

@dataclass
class ElectronPage:
    """Page-like object that proxies to Electron window"""
    window_id: str
    session: 'ElectronSession'
    _url: str = ""
    _title: str = ""
    
    @property
    def url(self) -> str:
        return self._url
        
    @property 
    def title(self) -> str:
        return self._title
        
    async def evaluate(self, script: str) -> Any:
        """Execute JavaScript in the page"""
        result = await self.session._send_command('execute_js', {
            'window_id': self.window_id,
            'script': script
        })
        return result
        
    def is_closed(self) -> bool:
        """Check if the page/window is closed"""
        return self.window_id not in self.session._active_windows
        
    async def close(self):
        """Close the page/window"""
        await self.session._send_command('close_window', {
            'window_id': self.window_id
        })

class ElectronSession:
    """Drop-in replacement for BrowserSession using Electron"""
    
    def __init__(
        self,
        browser_profile: BrowserProfile | None = None,
        ws_url: str = "ws://localhost:9222",
        **kwargs
    ):
        self.browser_profile = browser_profile or BrowserProfile()
        self.ws_url = ws_url
        self.ws: WebSocketClientProtocol | None = None
        self._pages: Dict[str, ElectronPage] = {}
        self._active_windows: set[str] = set()
        self._current_page_id: str | None = None
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self.id = str(uuid4())
        
        # Apply profile overrides
        for key, value in kwargs.items():
            if hasattr(self.browser_profile, key):
                setattr(self.browser_profile, key, value)
                
    async def start(self) -> 'ElectronSession':
        """Start the Electron session"""
        try:
            self.ws = await websockets.connect(self.ws_url)
            asyncio.create_task(self._message_handler())
            
            # Initialize browser with profile settings
            await self._send_command('initialize', {
                'profile': self.browser_profile.model_dump()
            })
            
            logger.info(f"Connected to Electron browser at {self.ws_url}")
            return self
            
        except Exception as e:
            logger.error(f"Failed to start Electron session: {e}")
            raise
            
    async def stop(self):
        """Stop the Electron session"""
        if self.ws:
            await self.ws.close()
            self.ws = None
            
    async def _message_handler(self):
        """Handle incoming messages from Electron"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                msg_id = data.get('id')
                
                if future := self._pending_responses.pop(msg_id, None):
                    if 'error' in data:
                        future.set_exception(Exception(data['error']['message']))
                    else:
                        future.set_result(data.get('result'))
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Electron WebSocket connection closed")
            
    async def _send_command(self, method: str, params: Dict[str, Any] = None) -> Any:
        """Send command to Electron and wait for response"""
        if not self.ws:
            raise RuntimeError("Not connected to Electron")
            
        msg_id = str(uuid4())
        future = asyncio.Future()
        self._pending_responses[msg_id] = future
        
        await self.ws.send(json.dumps({
            'id': msg_id,
            'method': method,
            'params': params or {}
        }))
        
        return await future
        
    async def navigate(self, url: str, new_tab: bool = False) -> Page:
        """Navigate to URL"""
        result = await self._send_command('navigate', {
            'url': url,
            'new_tab': new_tab
        })
        
        window_id = result['window_id']
        
        # Create or update page object
        if window_id not in self._pages:
            page = ElectronPage(window_id=window_id, session=self)
            self._pages[window_id] = page
            self._active_windows.add(window_id)
        else:
            page = self._pages[window_id]
            
        page._url = result['url']
        page._title = result.get('title', '')
        self._current_page_id = window_id
        
        return page
        
    async def get_current_page(self) -> Page | None:
        """Get current active page"""
        if self._current_page_id and self._current_page_id in self._pages:
            return self._pages[self._current_page_id]
        return None
        
    @property
    def tabs(self) -> List[Page]:
        """Get all open tabs/pages"""
        return list(self._pages.values())
        
    async def create_new_tab(self, url: str | None = None) -> Page:
        """Create new tab"""
        if url:
            return await self.navigate(url, new_tab=True)
        else:
            result = await self._send_command('create_tab', {})
            window_id = result['window_id']
            page = ElectronPage(window_id=window_id, session=self)
            self._pages[window_id] = page
            self._active_windows.add(window_id)
            return page
            
    async def switch_tab(self, tab_index: int) -> Page:
        """Switch to tab by index"""
        tabs = self.tabs
        if 0 <= tab_index < len(tabs):
            page = tabs[tab_index]
            await self._send_command('switch_tab', {
                'window_id': page.window_id
            })
            self._current_page_id = page.window_id
            return page
        raise IndexError(f"Tab index {tab_index} out of range")
        
    async def is_connected(self, restart: bool = True) -> bool:
        """Check if connected to Electron"""
        if self.ws and not self.ws.closed:
            try:
                # Ping to check connection
                await self._send_command('ping', {})
                return True
            except:
                pass
                
        if restart:
            try:
                await self.start()
                return True
            except:
                pass
                
        return False
        
    async def get_state_summary(self) -> BrowserStateSummary:
        """Get current browser state summary"""
        # Get DOM tree
        dom_script = """
        // Your DOM extraction script here
        // This would be the same as browser_use/dom/dom_tree/index.js
        """
        
        current_page = await self.get_current_page()
        if not current_page:
            return BrowserStateSummary(
                url="",
                title="No page",
                tabs=[],
                dom_tree={}
            )
            
        dom_tree = await current_page.evaluate(dom_script)
        
        # Get screenshot
        screenshot = await self.take_screenshot()
        
        # Get all tabs info
        tabs_info = []
        for page in self.tabs:
            tabs_info.append({
                'url': page.url,
                'title': page.title
            })
            
        return BrowserStateSummary(
            url=current_page.url,
            title=current_page.title,
            tabs=tabs_info,
            dom_tree=dom_tree,
            screenshot=screenshot
        )
        
    async def take_screenshot(self, full_page: bool = False) -> str | None:
        """Take screenshot of current page"""
        try:
            result = await self._send_command('screenshot', {
                'full_page': full_page
            })
            return result.get('data')  # Base64 encoded image
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
            
    async def execute_javascript(self, script: str) -> Any:
        """Execute JavaScript in current page"""
        current_page = await self.get_current_page()
        if current_page:
            return await current_page.evaluate(script)
        raise RuntimeError("No active page")
        
    # Stub methods that can be implemented as needed
    async def get_cookies(self) -> List[Dict]:
        """Get cookies (stub)"""
        return []
        
    async def go_back(self):
        """Go back in history (stub)"""
        pass
        
    async def save_storage_state(self, path=None):
        """Save storage state (stub)"""
        pass
```

### 1.4 Integration Configuration

**File**: `browser_use/browser/__init__.py` (modified)

```python
import os

# Existing imports
from .browser import Browser, BrowserConfig
from .context import BrowserContext, BrowserContextConfig
from .profile import BrowserProfile

# Conditional import based on environment
if os.getenv('USE_ELECTRON_BACKEND', '').lower() == 'true':
    from .electron_session import ElectronSession as BrowserSession
else:
    from .session import BrowserSession

__all__ = ['Browser', 'BrowserConfig', 'BrowserContext', 'BrowserContextConfig', 'BrowserSession', 'BrowserProfile']
```

## Part 2: Electron App Implementation

### 2.1 Main Process Architecture

**File**: `electron-app/main.js`

```javascript
const { app, BrowserWindow } = require('electron');
const WebSocket = require('ws');
const BrowserControlServer = require('./browser-control/server');
const UIBridgeServer = require('./ui-bridge/server');
const WindowManager = require('./window-manager');

class BrowserUseElectronApp {
    constructor() {
        this.windowManager = new WindowManager();
        this.browserControlServer = null;
        this.uiBridgeServer = null;
        this.mainWindow = null;
    }
    
    async initialize() {
        // Wait for app to be ready
        await app.whenReady();
        
        // Create main UI window
        this.mainWindow = new BrowserWindow({
            width: 1200,
            height: 800,
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false
            }
        });
        
        this.mainWindow.loadFile('renderer/index.html');
        
        // Start WebSocket servers
        this.browserControlServer = new BrowserControlServer(
            9222, 
            this.windowManager
        );
        await this.browserControlServer.start();
        
        this.uiBridgeServer = new UIBridgeServer(
            9223,
            this.mainWindow
        );
        await this.uiBridgeServer.start();
        
        console.log('Browser-Use Electron App initialized');
        console.log('Browser Control WebSocket: ws://localhost:9222');
        console.log('UI Bridge WebSocket: ws://localhost:9223');
    }
    
    shutdown() {
        if (this.browserControlServer) {
            this.browserControlServer.stop();
        }
        if (this.uiBridgeServer) {
            this.uiBridgeServer.stop();
        }
        app.quit();
    }
}

// Initialize app
const electronApp = new BrowserUseElectronApp();

app.on('ready', () => {
    electronApp.initialize();
});

app.on('window-all-closed', () => {
    electronApp.shutdown();
});
```

### 2.2 Browser Control Implementation

**File**: `electron-app/browser-control/server.js`

```javascript
const WebSocket = require('ws');
const CommandHandler = require('./command-handler');

class BrowserControlServer {
    constructor(port, windowManager) {
        this.port = port;
        this.windowManager = windowManager;
        this.wss = null;
        this.commandHandler = new CommandHandler(windowManager);
    }
    
    async start() {
        this.wss = new WebSocket.Server({ port: this.port });
        
        this.wss.on('connection', (ws) => {
            console.log('Browser control client connected');
            
            ws.on('message', async (message) => {
                try {
                    const request = JSON.parse(message);
                    const response = await this.handleRequest(request);
                    ws.send(JSON.stringify(response));
                } catch (error) {
                    ws.send(JSON.stringify({
                        id: request?.id,
                        error: {
                            message: error.message,
                            code: 'INTERNAL_ERROR'
                        }
                    }));
                }
            });
            
            ws.on('close', () => {
                console.log('Browser control client disconnected');
            });
        });
    }
    
    async handleRequest(request) {
        const { id, method, params } = request;
        
        try {
            const result = await this.commandHandler.execute(method, params);
            return { id, result };
        } catch (error) {
            return {
                id,
                error: {
                    message: error.message,
                    code: error.code || 'COMMAND_ERROR'
                }
            };
        }
    }
    
    stop() {
        if (this.wss) {
            this.wss.close();
        }
    }
}

module.exports = BrowserControlServer;
```

**File**: `electron-app/browser-control/command-handler.js`

```javascript
const { BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs').promises;

class CommandHandler {
    constructor(windowManager) {
        this.windowManager = windowManager;
    }
    
    async execute(method, params) {
        switch (method) {
            case 'initialize':
                return this.initialize(params);
            case 'navigate':
                return this.navigate(params);
            case 'execute_js':
                return this.executeJS(params);
            case 'screenshot':
                return this.screenshot(params);
            case 'click':
                return this.click(params);
            case 'type':
                return this.type(params);
            case 'create_tab':
                return this.createTab(params);
            case 'switch_tab':
                return this.switchTab(params);
            case 'close_window':
                return this.closeWindow(params);
            case 'ping':
                return { status: 'ok' };
            default:
                throw new Error(`Unknown method: ${method}`);
        }
    }
    
    async initialize(params) {
        const { profile } = params;
        // Apply browser profile settings
        this.windowManager.applyProfile(profile);
        return { status: 'initialized' };
    }
    
    async navigate(params) {
        const { url, new_tab } = params;
        
        let window;
        if (new_tab || !this.windowManager.getCurrentWindow()) {
            window = this.windowManager.createWindow();
        } else {
            window = this.windowManager.getCurrentWindow();
        }
        
        await window.loadURL(url);
        const title = await window.webContents.executeJavaScript('document.title');
        
        return {
            window_id: window.id,
            url: window.webContents.getURL(),
            title
        };
    }
    
    async executeJS(params) {
        const { window_id, script } = params;
        const window = this.windowManager.getWindow(window_id);
        
        if (!window) {
            throw new Error('Window not found');
        }
        
        return await window.webContents.executeJavaScript(script);
    }
    
    async screenshot(params) {
        const { full_page } = params;
        const window = this.windowManager.getCurrentWindow();
        
        if (!window) {
            throw new Error('No active window');
        }
        
        const image = await window.webContents.capturePage();
        const data = image.toDataURL();
        
        return { data };
    }
    
    async click(params) {
        const { selector, window_id } = params;
        const window = this.windowManager.getWindow(window_id);
        
        if (!window) {
            throw new Error('Window not found');
        }
        
        await window.webContents.executeJavaScript(`
            const element = document.querySelector('${selector}');
            if (element) {
                element.click();
                true;
            } else {
                throw new Error('Element not found');
            }
        `);
        
        return { status: 'clicked' };
    }
    
    async type(params) {
        const { selector, text, window_id } = params;
        const window = this.windowManager.getWindow(window_id);
        
        if (!window) {
            throw new Error('Window not found');
        }
        
        await window.webContents.executeJavaScript(`
            const element = document.querySelector('${selector}');
            if (element) {
                element.value = '${text}';
                element.dispatchEvent(new Event('input', { bubbles: true }));
                true;
            } else {
                throw new Error('Element not found');
            }
        `);
        
        return { status: 'typed' };
    }
    
    async createTab(params) {
        const window = this.windowManager.createWindow();
        return { window_id: window.id };
    }
    
    async switchTab(params) {
        const { window_id } = params;
        const window = this.windowManager.getWindow(window_id);
        
        if (!window) {
            throw new Error('Window not found');
        }
        
        window.focus();
        this.windowManager.setCurrentWindow(window);
        
        return { status: 'switched' };
    }
    
    async closeWindow(params) {
        const { window_id } = params;
        this.windowManager.closeWindow(window_id);
        return { status: 'closed' };
    }
}

module.exports = CommandHandler;
```

### 2.3 UI Bridge Implementation

**File**: `electron-app/ui-bridge/server.js`

```javascript
const WebSocket = require('ws');
const { ipcMain } = require('electron');

class UIBridgeServer {
    constructor(port, mainWindow) {
        this.port = port;
        this.mainWindow = mainWindow;
        this.wss = null;
        this.clients = new Set();
        this.setupIPCHandlers();
    }
    
    setupIPCHandlers() {
        // Handle responses from renderer process
        ipcMain.on('user-input-response', (event, data) => {
            this.broadcast({
                type: 'user_input',
                input_id: data.input_id,
                value: data.value
            });
        });
        
        ipcMain.on('ui-command', (event, command, params) => {
            this.broadcast({
                type: 'command',
                command,
                params
            });
        });
    }
    
    async start() {
        this.wss = new WebSocket.Server({ port: this.port });
        
        this.wss.on('connection', (ws) => {
            console.log('UI Bridge client connected');
            this.clients.add(ws);
            
            ws.on('message', async (message) => {
                try {
                    const data = JSON.parse(message);
                    await this.handleMessage(data, ws);
                } catch (error) {
                    console.error('Error handling UI message:', error);
                }
            });
            
            ws.on('close', () => {
                console.log('UI Bridge client disconnected');
                this.clients.delete(ws);
            });
        });
    }
    
    async handleMessage(data, ws) {
        switch (data.type) {
            case 'agent_event':
                // Forward to renderer process
                this.mainWindow.webContents.send('agent-event', data);
                break;
                
            case 'input_request':
                // Show input dialog in renderer
                this.mainWindow.webContents.send('input-request', data);
                break;
                
            case 'notification':
                // Show notification
                this.mainWindow.webContents.send('notification', data);
                break;
                
            default:
                console.warn('Unknown message type:', data.type);
        }
    }
    
    broadcast(data) {
        const message = JSON.stringify(data);
        this.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(message);
            }
        });
    }
    
    stop() {
        if (this.wss) {
            this.wss.close();
        }
    }
}

module.exports = UIBridgeServer;
```

### 2.4 Window Manager

**File**: `electron-app/window-manager.js`

```javascript
const { BrowserWindow, BrowserView } = require('electron');

class WindowManager {
    constructor() {
        this.windows = new Map();
        this.currentWindowId = null;
        this.profile = {};
        this.windowIdCounter = 1;
    }
    
    applyProfile(profile) {
        this.profile = profile;
        // Apply profile settings to all windows
        this.windows.forEach(window => {
            this.applyProfileToWindow(window, profile);
        });
    }
    
    applyProfileToWindow(window, profile) {
        if (profile.viewport) {
            window.setSize(profile.viewport.width, profile.viewport.height);
        }
        
        if (profile.user_agent) {
            window.webContents.setUserAgent(profile.user_agent);
        }
        
        // Apply other profile settings...
    }
    
    createWindow() {
        const windowId = `window_${this.windowIdCounter++}`;
        
        const window = new BrowserWindow({
            width: this.profile.viewport?.width || 1280,
            height: this.profile.viewport?.height || 720,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                webSecurity: true
            },
            show: !this.profile.headless
        });
        
        window.id = windowId;
        this.windows.set(windowId, window);
        this.currentWindowId = windowId;
        
        this.applyProfileToWindow(window, this.profile);
        
        window.on('closed', () => {
            this.windows.delete(windowId);
            if (this.currentWindowId === windowId) {
                this.currentWindowId = null;
            }
        });
        
        return window;
    }
    
    getWindow(windowId) {
        return this.windows.get(windowId);
    }
    
    getCurrentWindow() {
        if (this.currentWindowId) {
            return this.windows.get(this.currentWindowId);
        }
        return null;
    }
    
    setCurrentWindow(window) {
        this.currentWindowId = window.id;
    }
    
    closeWindow(windowId) {
        const window = this.windows.get(windowId);
        if (window) {
            window.close();
        }
    }
    
    getAllWindows() {
        return Array.from(this.windows.values());
    }
}

module.exports = WindowManager;
```

### 2.5 Renderer Process UI

**File**: `electron-app/renderer/index.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>Browser-Use UI</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>Browser-Use Agent</h1>
            <div class="controls">
                <button id="pause-btn">Pause</button>
                <button id="resume-btn" disabled>Resume</button>
                <button id="stop-btn">Stop</button>
            </div>
        </header>
        
        <main>
            <div class="panel" id="task-panel">
                <h2>Current Task</h2>
                <div id="task-info"></div>
            </div>
            
            <div class="panel" id="steps-panel">
                <h2>Execution Steps</h2>
                <div id="steps-list"></div>
            </div>
            
            <div class="panel" id="browser-state-panel">
                <h2>Browser State</h2>
                <div id="browser-info"></div>
            </div>
        </main>
        
        <div id="input-dialog" class="dialog hidden">
            <div class="dialog-content">
                <h3 id="input-prompt"></h3>
                <div id="input-options"></div>
                <input type="text" id="input-field" class="hidden">
                <button id="submit-input">Submit</button>
            </div>
        </div>
        
        <div id="notifications"></div>
    </div>
    
    <script src="renderer.js"></script>
</body>
</html>
```

**File**: `electron-app/renderer/renderer.js`

```javascript
const { ipcRenderer } = require('electron');

class BrowserUseUI {
    constructor() {
        this.currentInputRequest = null;
        this.steps = [];
        this.setupEventHandlers();
        this.setupIPCHandlers();
    }
    
    setupEventHandlers() {
        // Control buttons
        document.getElementById('pause-btn').addEventListener('click', () => {
            this.sendCommand('pause');
            this.updateControlButtons('paused');
        });
        
        document.getElementById('resume-btn').addEventListener('click', () => {
            this.sendCommand('resume');
            this.updateControlButtons('running');
        });
        
        document.getElementById('stop-btn').addEventListener('click', () => {
            this.sendCommand('stop');
            this.updateControlButtons('stopped');
        });
        
        // Input dialog
        document.getElementById('submit-input').addEventListener('click', () => {
            this.submitInput();
        });
    }
    
    setupIPCHandlers() {
        // Handle agent events
        ipcRenderer.on('agent-event', (event, data) => {
            this.handleAgentEvent(data);
        });
        
        // Handle input requests
        ipcRenderer.on('input-request', (event, data) => {
            this.showInputDialog(data);
        });
        
        // Handle notifications
        ipcRenderer.on('notification', (event, data) => {
            this.showNotification(data);
        });
    }
    
    handleAgentEvent(data) {
        const { event, data: eventData } = data;
        
        switch (event) {
            case 'CreateAgentSessionEvent':
                this.updateTaskInfo(eventData);
                break;
                
            case 'CreateAgentStepEvent':
                this.addStep(eventData);
                break;
                
            case 'UpdateAgentTaskEvent':
                this.updateTaskStatus(eventData);
                break;
                
            default:
                console.log('Agent event:', event, eventData);
        }
    }
    
    updateTaskInfo(data) {
        const taskPanel = document.getElementById('task-info');
        taskPanel.innerHTML = `
            <div class="task-item">
                <strong>Task:</strong> ${data.task || 'N/A'}
            </div>
            <div class="task-item">
                <strong>Session ID:</strong> ${data.id || 'N/A'}
            </div>
            <div class="task-item">
                <strong>Status:</strong> <span class="status running">Running</span>
            </div>
        `;
    }
    
    addStep(data) {
        const step = {
            id: data.id,
            action: data.action,
            timestamp: new Date().toLocaleTimeString(),
            status: 'completed'
        };
        
        this.steps.push(step);
        this.renderSteps();
    }
    
    renderSteps() {
        const stepsList = document.getElementById('steps-list');
        stepsList.innerHTML = this.steps.map(step => `
            <div class="step-item">
                <span class="step-time">${step.timestamp}</span>
                <span class="step-action">${step.action}</span>
                <span class="step-status ${step.status}">${step.status}</span>
            </div>
        `).join('');
        
        // Scroll to bottom
        stepsList.scrollTop = stepsList.scrollHeight;
    }
    
    showInputDialog(data) {
        this.currentInputRequest = data;
        const dialog = document.getElementById('input-dialog');
        const prompt = document.getElementById('input-prompt');
        const optionsDiv = document.getElementById('input-options');
        const inputField = document.getElementById('input-field');
        
        prompt.textContent = data.prompt;
        
        if (data.options && data.options.length > 0) {
            // Show options as buttons
            inputField.classList.add('hidden');
            optionsDiv.classList.remove('hidden');
            optionsDiv.innerHTML = data.options.map(option => 
                `<button class="option-btn" data-value="${option}">${option}</button>`
            ).join('');
            
            // Add click handlers
            optionsDiv.querySelectorAll('.option-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    this.submitInput(e.target.dataset.value);
                });
            });
        } else {
            // Show text input
            optionsDiv.classList.add('hidden');
            inputField.classList.remove('hidden');
            inputField.value = '';
            inputField.focus();
        }
        
        dialog.classList.remove('hidden');
    }
    
    submitInput(value) {
        if (!value) {
            value = document.getElementById('input-field').value;
        }
        
        if (this.currentInputRequest) {
            ipcRenderer.send('user-input-response', {
                input_id: this.currentInputRequest.input_id,
                value: value
            });
            
            this.currentInputRequest = null;
            document.getElementById('input-dialog').classList.add('hidden');
        }
    }
    
    showNotification(data) {
        const notifications = document.getElementById('notifications');
        const notification = document.createElement('div');
        notification.className = `notification ${data.level}`;
        notification.innerHTML = `
            <strong>${data.title}</strong>
            <p>${data.message}</p>
        `;
        
        notifications.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
    
    sendCommand(command, params = {}) {
        ipcRenderer.send('ui-command', command, params);
    }
    
    updateControlButtons(state) {
        const pauseBtn = document.getElementById('pause-btn');
        const resumeBtn = document.getElementById('resume-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        switch (state) {
            case 'running':
                pauseBtn.disabled = false;
                resumeBtn.disabled = true;
                stopBtn.disabled = false;
                break;
            case 'paused':
                pauseBtn.disabled = true;
                resumeBtn.disabled = false;
                stopBtn.disabled = false;
                break;
            case 'stopped':
                pauseBtn.disabled = true;
                resumeBtn.disabled = true;
                stopBtn.disabled = true;
                break;
        }
    }
}

// Initialize UI
const ui = new BrowserUseUI();
```

**File**: `electron-app/renderer/styles.css`

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
}

#app {
    display: flex;
    flex-direction: column;
    height: 100vh;
}

header {
    background: #2c3e50;
    color: white;
    padding: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

h1 {
    font-size: 1.5rem;
}

.controls button {
    background: #3498db;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    margin-left: 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.3s;
}

.controls button:hover:not(:disabled) {
    background: #2980b9;
}

.controls button:disabled {
    background: #7f8c8d;
    cursor: not-allowed;
}

main {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 2fr 1fr;
    gap: 1rem;
    padding: 1rem;
    overflow: hidden;
}

.panel {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    overflow-y: auto;
}

.panel h2 {
    font-size: 1.2rem;
    margin-bottom: 1rem;
    color: #2c3e50;
}

.task-item {
    margin-bottom: 0.5rem;
}

.task-item strong {
    display: inline-block;
    width: 100px;
}

.status {
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
}

.status.running {
    background: #27ae60;
    color: white;
}

.status.paused {
    background: #f39c12;
    color: white;
}

.status.stopped {
    background: #e74c3c;
    color: white;
}

.step-item {
    display: flex;
    align-items: center;
    padding: 0.5rem;
    border-bottom: 1px solid #ecf0f1;
}

.step-time {
    font-size: 0.8rem;
    color: #7f8c8d;
    margin-right: 1rem;
    min-width: 80px;
}

.step-action {
    flex: 1;
}

.step-status {
    font-size: 0.8rem;
}

.dialog {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.dialog.hidden {
    display: none;
}

.dialog-content {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    min-width: 400px;
}

.dialog h3 {
    margin-bottom: 1rem;
}

#input-field {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    margin-bottom: 1rem;
}

#input-options {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.option-btn {
    flex: 1;
    padding: 0.5rem 1rem;
    background: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.option-btn:hover {
    background: #2980b9;
}

#submit-input {
    background: #27ae60;
    color: white;
    border: none;
    padding: 0.5rem 1.5rem;
    border-radius: 4px;
    cursor: pointer;
}

#submit-input:hover {
    background: #229954;
}

#notifications {
    position: fixed;
    top: 80px;
    right: 20px;
    z-index: 999;
}

.notification {
    background: white;
    padding: 1rem;
    margin-bottom: 0.5rem;
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    min-width: 300px;
    animation: slideIn 0.3s ease;
}

.notification.info {
    border-left: 4px solid #3498db;
}

.notification.warning {
    border-left: 4px solid #f39c12;
}

.notification.error {
    border-left: 4px solid #e74c3c;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.hidden {
    display: none !important;
}
```

## WebSocket Message Protocol Specification

### Browser Control Protocol (Port 9222)

#### Request Format
```typescript
interface BrowserControlRequest {
    id: string;              // Unique request ID
    method: string;          // Method name
    params: Record<string, any>; // Method parameters
}
```

#### Response Format
```typescript
interface BrowserControlResponse {
    id: string;              // Matching request ID
    result?: any;            // Success result
    error?: {                // Error details (if failed)
        message: string;
        code: string;
    };
}
```

#### Available Methods
- `initialize`: Initialize browser with profile settings
- `navigate`: Navigate to URL
- `execute_js`: Execute JavaScript in page
- `screenshot`: Capture screenshot
- `click`: Click element by selector
- `type`: Type text into element
- `create_tab`: Create new tab/window
- `switch_tab`: Switch to specific tab
- `close_window`: Close tab/window
- `ping`: Health check

### UI Bridge Protocol (Port 9223)

#### Agent → UI Events
```typescript
interface AgentEvent {
    type: 'agent_event';
    event: string;           // Event name
    data: any;              // Event data
    timestamp: number;      // Event timestamp
}
```

#### UI → Agent Commands
```typescript
interface UICommand {
    type: 'command';
    command: 'pause' | 'resume' | 'stop';
    params?: Record<string, any>;
}
```

#### Input Request/Response
```typescript
interface InputRequest {
    type: 'input_request';
    input_id: string;       // Unique input ID
    prompt: string;         // Question for user
    options?: string[];     // Optional choices
}

interface UserInputResponse {
    type: 'user_input';
    input_id: string;       // Matching input ID
    value: string;          // User's response
}
```

#### Notifications
```typescript
interface Notification {
    type: 'notification';
    title: string;
    message: string;
    level: 'info' | 'warning' | 'error';
}
```

## Implementation Steps

### Phase 1: Core Infrastructure (Days 1-2)
1. Set up Electron app structure
2. Implement WebSocket servers
3. Create basic window management
4. Test WebSocket connectivity

### Phase 2: Browser Control (Days 3-4)
1. Implement ElectronSession class
2. Create command handlers for navigation, clicks, typing
3. Add screenshot and JavaScript execution
4. Test with simple browser-use scripts

### Phase 3: UI Bridge (Days 5-6)
1. Implement ElectronUIBridge class
2. Create UI event forwarding
3. Add input request handling
4. Build basic renderer UI

### Phase 4: Human-in-the-Loop (Days 7-8)
1. Create custom actions for user interaction
2. Implement input dialogs in UI
3. Add pause/resume functionality
4. Test complete workflows

### Phase 5: Polish & Testing (Days 9-10)
1. Error handling and reconnection logic
2. Performance optimization
3. Comprehensive testing
4. Documentation

## Example Usage

### Basic Script
```python
import asyncio
from browser_use import Agent
from browser_use.llm.openai import ChatOpenAI
from browser_use.electron import ElectronUIBridge, ElectronSession, actions

async def main():
    # Initialize UI bridge
    ui_bridge = ElectronUIBridge()
    await ui_bridge.connect()
    
    # Set up UI bridge for actions
    actions.ui_bridge = ui_bridge
    
    # Create controller with Electron actions
    from browser_use import Controller
    controller = Controller()
    
    controller.action("Ask user for input")(actions.ask_user_electron)
    controller.action("Confirm action")(actions.confirm_action_electron)
    controller.action("Notify user")(actions.notify_user_electron)
    
    # Create agent with Electron backend
    agent = Agent(
        task="Help me book a flight to Paris",
        llm=ChatOpenAI(model="gpt-4"),
        controller=controller,
        browser_session=ElectronSession()
    )
    
    # Subscribe UI to agent events
    ui_bridge.subscribe_to_agent_events(agent)
    
    # Handle UI commands
    async def handle_pause():
        agent.pause()
        
    async def handle_resume():
        agent.resume()
        
    ui_bridge.event_bus.on('ui_command_pause', lambda _: asyncio.create_task(handle_pause()))
    ui_bridge.event_bus.on('ui_command_resume', lambda _: asyncio.create_task(handle_resume()))
    
    # Run agent
    result = await agent.run()
    print(f"Task completed: {result}")
    
    # Cleanup
    await ui_bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Environment Setup
```bash
# Python side
export USE_ELECTRON_BACKEND=true
pip install websockets

# Electron side
npm install electron ws
npm start
```

## Architecture Benefits

1. **Separation of Concerns**: Browser control and UI are independent
2. **Flexibility**: Can use any UI framework in Electron
3. **Scalability**: WebSocket architecture supports multiple clients
4. **Maintainability**: Clean interfaces between components
5. **Extensibility**: Easy to add new commands and events

## Troubleshooting

### Common Issues
1. **WebSocket Connection Failed**: Check ports 9222/9223 are available
2. **ElectronSession Not Found**: Ensure USE_ELECTRON_BACKEND=true
3. **UI Not Updating**: Verify event subscription is active
4. **Input Timeout**: Increase timeout in request_user_input()

### Debugging Tips
1. Enable debug logging: `export DEBUG=browser-use:*`
2. Monitor WebSocket traffic with Chrome DevTools
3. Check Electron console for JavaScript errors
4. Use `--inspect` flag for Node.js debugging

## Future Enhancements

1. **Multi-window Support**: Handle multiple browser windows in UI
2. **Session Recording**: Record and replay agent sessions
3. **Advanced Dialogs**: File pickers, color choosers, etc.
4. **Performance Metrics**: Show timing and resource usage
5. **Plugin System**: Allow custom UI components
6. **Remote Control**: Control agent from web interface

This implementation plan provides a complete roadmap for integrating browser-use with an Electron application, enabling rich UI interactions and human-in-the-loop capabilities.