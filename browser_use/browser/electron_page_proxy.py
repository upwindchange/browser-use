"""
Minimal ElectronPage proxy implementation with only essential Playwright Page methods.
Provides WebSocket examples for each method, even if stubbed.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Callable, List
from uuid import uuid4

logger = logging.getLogger(__name__)


class ElectronKeyboard:
	"""Minimal keyboard input proxy for ElectronPage"""
	
	def __init__(self, page: 'ElectronPageProxy'):
		self._page = page
	
	async def press(self, key: str, delay: float = 0) -> None:
		"""Press a key
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "keyboard.press",
			"params": {
				"window_id": "window-123",
				"key": "Enter",
				"delay": 0
			}
		}
		
		Electron implementation:
		```javascript
		case 'keyboard.press':
			const window = getWindow(params.window_id);
			await window.webContents.sendInputEvent({
				type: 'keyDown',
				keyCode: params.key
			});
			await window.webContents.sendInputEvent({
				type: 'keyUp',
				keyCode: params.key
			});
			return { success: true };
		```
		"""
		await self._page._send_command('keyboard.press', {
			'window_id': self._page.window_id,
			'key': key,
			'delay': delay
		})
	
	async def type(self, text: str, delay: float = 0) -> None:
		"""Type text with optional delay between keystrokes
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "keyboard.type",
			"params": {
				"window_id": "window-123",
				"text": "Hello World",
				"delay": 50
			}
		}
		
		Electron implementation:
		```javascript
		case 'keyboard.type':
			const window = getWindow(params.window_id);
			for (const char of params.text) {
				await window.webContents.sendInputEvent({
					type: 'char',
					keyCode: char
				});
				if (params.delay > 0) {
					await new Promise(resolve => setTimeout(resolve, params.delay));
				}
			}
			return { success: true };
		```
		"""
		await self._page._send_command('keyboard.type', {
			'window_id': self._page.window_id,
			'text': text,
			'delay': delay
		})


class ElectronMouse:
	"""Minimal mouse input proxy for ElectronPage"""
	
	def __init__(self, page: 'ElectronPageProxy'):
		self._page = page
	
	async def click(self, x: float, y: float, options: Optional[Dict[str, Any]] = None) -> None:
		"""Click at position
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "mouse.click",
			"params": {
				"window_id": "window-123",
				"x": 100,
				"y": 200,
				"options": {
					"button": "left",
					"clickCount": 1
				}
			}
		}
		
		Electron implementation:
		```javascript
		case 'mouse.click':
			const window = getWindow(params.window_id);
			const button = params.options?.button || 'left';
			const clickCount = params.options?.clickCount || 1;
			
			await window.webContents.sendInputEvent({
				type: 'mouseDown',
				x: params.x,
				y: params.y,
				button: button,
				clickCount: clickCount
			});
			await window.webContents.sendInputEvent({
				type: 'mouseUp',
				x: params.x,
				y: params.y,
				button: button,
				clickCount: clickCount
			});
			return { success: true };
		```
		"""
		# Stub implementation
		logger.warning(f"ElectronMouse.click({x}, {y}) - STUB")
	
	async def move(self, x: float, y: float, options: Optional[Dict[str, Any]] = None) -> None:
		"""Move mouse - REQUIRED for drag operations"""
		await self._page._send_command('mouse.move', {
			'window_id': self._page.window_id,
			'x': x,
			'y': y,
			'options': options or {}
		})
	
	async def down(self, options: Optional[Dict[str, Any]] = None) -> None:
		"""Mouse down - REQUIRED for drag operations"""
		await self._page._send_command('mouse.down', {
			'window_id': self._page.window_id,
			'options': options or {}
		})
	
	async def up(self, options: Optional[Dict[str, Any]] = None) -> None:
		"""Mouse up - REQUIRED for drag operations"""
		await self._page._send_command('mouse.up', {
			'window_id': self._page.window_id,
			'options': options or {}
		})


class ElectronBrowserContextStub:
	"""Minimal BrowserContext stub that only implements what's actually used"""
	
	def __init__(self, session: Any):
		self._session = session
		self.browser = None  # Some code might check context.browser
	
	async def new_cdp_session(self, page: 'ElectronPageProxy') -> 'ElectronCDPSessionStub':
		"""Create a CDP session stub
		
		In the real implementation, this would create a Chrome DevTools Protocol
		session for advanced browser control. For Electron, we return a stub.
		"""
		logger.warning("CDP session requested - returning stub. CDP operations will not work.")
		return ElectronCDPSessionStub(page.window_id, self._session)
	
	# Any other BrowserContext methods can return stubs
	def __getattr__(self, name: str) -> Any:
		logger.warning(f"ElectronBrowserContextStub.{name}() not implemented")
		return lambda *args, **kwargs: None


class ElectronCDPSessionStub:
	"""Minimal CDP session stub"""
	
	def __init__(self, window_id: str, session: Any):
		self.window_id = window_id
		self._session = session
	
	async def send(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		"""Stub for CDP commands
		
		Real CDP commands like 'Browser.setWindowBounds', 'Page.captureScreenshot', etc.
		would be translated to equivalent Electron commands here.
		"""
		logger.warning(f"CDP command stubbed: {method} with params {params}")
		
		# Return minimal valid responses to prevent crashes
		if method == 'Browser.getWindowForTarget':
			return {'windowId': self.window_id}
		elif method == 'Target.getTargets':
			return {'targetInfos': []}
		elif method == 'Page.captureScreenshot':
			return {'data': ''}  # Empty base64 string
		
		return {}
	
	async def detach(self) -> None:
		"""Detach the CDP session"""
		pass


class ElectronLocator:
	"""Minimal locator implementation for ElectronPage"""
	
	def __init__(self, page: 'ElectronPageProxy', selector: str, options: Optional[Dict[str, Any]] = None):
		self._page = page
		self._selector = selector
		self._options = options or {}
	
	async def click(self, options: Optional[Dict[str, Any]] = None) -> None:
		"""Click the element"""
		# Delegate to page click method
		await self._page.click(self._selector, options)
	
	async def fill(self, value: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Fill the element"""
		# Delegate to page fill method
		await self._page.fill(self._selector, value, options)
	
	async def type(self, text: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Type into the element"""
		# Delegate to page type method
		await self._page.type(self._selector, text, options)
	
	async def press(self, key: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Press key on element"""
		# Delegate to page press method
		await self._page.press(self._selector, key, options)
	
	async def inner_text(self) -> str:
		"""Get inner text"""
		return await self._page.inner_text(self._selector)
	
	async def is_visible(self) -> bool:
		"""Check if visible"""
		return await self._page.is_visible(self._selector)
	
	# Add more methods as needed by tests/examples
	def __getattr__(self, name: str) -> Any:
		"""Catch-all for unimplemented locator methods"""
		logger.warning(f"ElectronLocator.{name}() not implemented - returning stub")
		
		async def async_stub(*args, **kwargs):
			logger.debug(f"LOCATOR STUB: {name}({args}, {kwargs})")
			return None
		
		return async_stub


class ElectronPageProxy:
	"""
	Minimal proxy implementation of essential Playwright Page methods for Electron.
	Only implements methods actually used by browser-use codebase.
	"""
	
	def __init__(self, window_id: str, session: Any):
		self.window_id = window_id
		self._session = session
		self._keyboard = ElectronKeyboard(self)
		self._mouse = ElectronMouse(self)
		
		# Cached properties
		self._url: str = ""
		self._title: str = ""
		self._is_closed: bool = False
	
	async def _send_command(self, method: str, params: Dict[str, Any]) -> Any:
		"""Send command to Electron via session"""
		return await self._session._send_command(method, params)
	
	# ===== Essential Properties =====
	
	@property
	def url(self) -> str:
		"""Get current URL - cached from navigation/updates"""
		return self._url
	
	async def title(self) -> str:
		"""Get page title - Playwright expects this to be async
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.title",
			"params": {
				"window_id": "window-123"
			}
		}
		
		Expected response:
		{
			"id": "uuid-here",
			"result": {
				"title": "Example Page Title"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.title':
			const window = getWindow(params.window_id);
			const title = window.webContents.getTitle();
			return { title };
		```
		"""
		result = await self._send_command('page.title', {
			'window_id': self.window_id
		})
		self._title = result.get('title', '')
		return self._title
	
	@property
	def keyboard(self) -> ElectronKeyboard:
		"""Get keyboard controller"""
		return self._keyboard
	
	@property
	def mouse(self) -> ElectronMouse:
		"""Get mouse controller"""
		return self._mouse
	
	# ===== Essential Methods Used by Browser-Use =====
	
	async def evaluate(self, expression: str, arg: Any = None) -> Any:
		"""Execute JavaScript in page context
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.evaluate",
			"params": {
				"window_id": "window-123",
				"expression": "document.title",
				"arg": null
			}
		}
		
		Expected response:
		{
			"id": "uuid-here",
			"result": {
				"value": "Example Page Title"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.evaluate':
			const window = getWindow(params.window_id);
			try {
				const result = await window.webContents.executeJavaScript(
					params.expression,
					false  // userGesture
				);
				return { value: result };
			} catch (error) {
				throw new Error(`Evaluation failed: ${error.message}`);
			}
		```
		"""
		result = await self._send_command('page.evaluate', {
			'window_id': self.window_id,
			'expression': expression,
			'arg': arg
		})
		return result.get('value')
	
	async def content(self) -> str:
		"""Get full HTML content
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.content",
			"params": {
				"window_id": "window-123"
			}
		}
		
		Expected response:
		{
			"id": "uuid-here",
			"result": {
				"content": "<html>...</html>"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.content':
			const window = getWindow(params.window_id);
			const html = await window.webContents.executeJavaScript(
				'document.documentElement.outerHTML'
			);
			return { content: html };
		```
		"""
		result = await self._send_command('page.content', {
			'window_id': self.window_id
		})
		return result.get('content', '')
	
	async def wait_for_load_state(self, state: str = 'load', options: Optional[Dict[str, Any]] = None) -> None:
		"""Wait for load state
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.waitForLoadState",
			"params": {
				"window_id": "window-123",
				"state": "domcontentloaded",
				"options": {
					"timeout": 30000
				}
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.waitForLoadState':
			const window = getWindow(params.window_id);
			const timeout = params.options?.timeout || 30000;
			
			return new Promise((resolve, reject) => {
				const timer = setTimeout(() => {
					reject(new Error('Timeout waiting for load state'));
				}, timeout);
				
				const checkState = () => {
					if (params.state === 'domcontentloaded') {
						window.webContents.once('dom-ready', () => {
							clearTimeout(timer);
							resolve({ success: true });
						});
					} else if (params.state === 'load') {
						window.webContents.once('did-finish-load', () => {
							clearTimeout(timer);
							resolve({ success: true });
						});
					}
				};
				
				checkState();
			});
		```
		"""
		await self._send_command('page.waitForLoadState', {
			'window_id': self.window_id,
			'state': state,
			'options': options or {}
		})
	
	async def wait_for_selector(self, selector: str, options: Optional[Dict[str, Any]] = None) -> Optional[Any]:
		"""Wait for element to appear
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.waitForSelector",
			"params": {
				"window_id": "window-123",
				"selector": "#my-element",
				"options": {
					"timeout": 30000,
					"state": "visible"
				}
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.waitForSelector':
			const window = getWindow(params.window_id);
			const timeout = params.options?.timeout || 30000;
			const state = params.options?.state || 'attached';
			const startTime = Date.now();
			
			while (Date.now() - startTime < timeout) {
				const result = await window.webContents.executeJavaScript(`
					(() => {
						const element = document.querySelector('${params.selector}');
						if (!element) return { found: false };
						
						const isVisible = element.offsetParent !== null;
						return {
							found: true,
							visible: isVisible,
							attached: true
						};
					})()
				`);
				
				if (result.found && (state === 'attached' || 
					(state === 'visible' && result.visible))) {
					return { found: true };
				}
				
				await new Promise(resolve => setTimeout(resolve, 100));
			}
			
			throw new Error(\`Timeout waiting for selector: \${params.selector}\`);
		```
		"""
		# Stub implementation
		logger.warning(f"ElectronPageProxy.wait_for_selector('{selector}') - STUB")
		return None
	
	async def screenshot(self, options: Optional[Dict[str, Any]] = None) -> bytes:
		"""Take screenshot
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.screenshot",
			"params": {
				"window_id": "window-123",
				"options": {
					"fullPage": false,
					"path": null,
					"type": "png"
				}
			}
		}
		
		Expected response:
		{
			"id": "uuid-here",
			"result": {
				"data": "base64-encoded-image-data"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.screenshot':
			const window = getWindow(params.window_id);
			const fullPage = params.options?.fullPage || false;
			
			let image;
			if (fullPage) {
				// Capture full page by scrolling
				const pageSize = await window.webContents.executeJavaScript(`
					({ 
						width: document.documentElement.scrollWidth,
						height: document.documentElement.scrollHeight
					})
				`);
				image = await window.webContents.capturePage({
					x: 0,
					y: 0,
					width: pageSize.width,
					height: pageSize.height
				});
			} else {
				// Capture visible viewport
				image = await window.webContents.capturePage();
			}
			
			const buffer = image.toPNG();
			return { data: buffer.toString('base64') };
		```
		"""
		result = await self._send_command('page.screenshot', {
			'window_id': self.window_id,
			'options': options or {}
		})
		# Convert base64 to bytes
		import base64
		return base64.b64decode(result.get('data', ''))
	
	async def close(self) -> None:
		"""Close the page
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.close",
			"params": {
				"window_id": "window-123"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.close':
			const window = getWindow(params.window_id);
			window.close();
			removeWindow(params.window_id);
			return { success: true };
		```
		"""
		await self._send_command('page.close', {
			'window_id': self.window_id
		})
		self._is_closed = True
	
	def is_closed(self) -> bool:
		"""Check if page is closed"""
		return self._is_closed or (self.window_id not in self._session._active_windows)
	
	async def reload(self, options: Optional[Dict[str, Any]] = None) -> Optional[Any]:
		"""Reload the page
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.reload",
			"params": {
				"window_id": "window-123",
				"options": {
					"waitUntil": "load"
				}
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.reload':
			const window = getWindow(params.window_id);
			window.webContents.reload();
			
			// Wait for reload to complete if requested
			if (params.options?.waitUntil) {
				await new Promise((resolve) => {
					window.webContents.once('did-finish-load', resolve);
				});
			}
			
			return { success: true };
		```
		"""
		return await self._send_command('page.reload', {
			'window_id': self.window_id,
			'options': options or {}
		})
	
	async def goto(self, url: str, options: Optional[Dict[str, Any]] = None) -> Optional[Any]:
		"""Navigate to URL (used indirectly through session)
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.goto",
			"params": {
				"window_id": "window-123",
				"url": "https://example.com",
				"options": {
					"timeout": 30000,
					"waitUntil": "load"
				}
			}
		}
		
		Expected response:
		{
			"id": "uuid-here",
			"result": {
				"url": "https://example.com",
				"status": 200
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.goto':
			const window = getWindow(params.window_id);
			const timeout = params.options?.timeout || 30000;
			
			return new Promise((resolve, reject) => {
				const timer = setTimeout(() => {
					reject(new Error('Navigation timeout'));
				}, timeout);
				
				let responseDetails = null;
				
				// Listen for response
				const handleResponse = (event, status, newURL, originalURL, 
					httpResponseCode, requestMethod, referrer, headers) => {
					if (newURL === params.url || originalURL === params.url) {
						responseDetails = {
							status: httpResponseCode,
							url: newURL
						};
					}
				};
				
				window.webContents.on('did-get-response-details', handleResponse);
				
				// Listen for load complete
				window.webContents.once('did-finish-load', () => {
					clearTimeout(timer);
					window.webContents.off('did-get-response-details', handleResponse);
					
					resolve({
						url: window.webContents.getURL(),
						status: responseDetails?.status || 200
					});
				});
				
				// Navigate
				window.webContents.loadURL(params.url);
			});
		```
		"""
		result = await self._send_command('page.goto', {
			'window_id': self.window_id,
			'url': url,
			'options': options or {}
		})
		self._url = result.get('url', url)
		return result
	
	async def go_back(self, options: Optional[Dict[str, Any]] = None) -> Optional[Any]:
		"""Navigate back in history - REQUIRED by browser-use controller
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.goBack",
			"params": {
				"window_id": "window-123",
				"options": {
					"timeout": 30000,
					"waitUntil": "load"
				}
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.goBack':
			const window = getWindow(params.window_id);
			if (window.webContents.canGoBack()) {
				window.webContents.goBack();
				
				if (params.options?.waitUntil) {
					await new Promise((resolve) => {
						window.webContents.once('did-finish-load', resolve);
					});
				}
				return { success: true };
			}
			return { success: false, reason: 'Cannot go back' };
		```
		"""
		return await self._send_command('page.goBack', {
			'window_id': self.window_id,
			'options': options or {}
		})
	
	async def go_forward(self, options: Optional[Dict[str, Any]] = None) -> Optional[Any]:
		"""Navigate forward in history - REQUIRED by browser-use controller
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.goForward",
			"params": {
				"window_id": "window-123",
				"options": {
					"timeout": 30000,
					"waitUntil": "load"
				}
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.goForward':
			const window = getWindow(params.window_id);
			if (window.webContents.canGoForward()) {
				window.webContents.goForward();
				
				if (params.options?.waitUntil) {
					await new Promise((resolve) => {
						window.webContents.once('did-finish-load', resolve);
					});
				}
				return { success: true };
			}
			return { success: false, reason: 'Cannot go forward' };
		```
		"""
		return await self._send_command('page.goForward', {
			'window_id': self.window_id,
			'options': options or {}
		})
	
	# ===== DOM Query Methods (REQUIRED) =====
	
	async def query_selector(self, selector: str) -> Optional[Any]:
		"""Query single element - REQUIRED for element finding
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.querySelector",
			"params": {
				"window_id": "window-123",
				"selector": ".my-class"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.querySelector':
			const window = getWindow(params.window_id);
			const exists = await window.webContents.executeJavaScript(`
				!!document.querySelector('${params.selector}')
			`);
			return { element: exists ? { selector: params.selector } : null };
		```
		"""
		result = await self._send_command('page.querySelector', {
			'window_id': self.window_id,
			'selector': selector
		})
		return result.get('element')
	
	async def query_selector_all(self, selector: str) -> list[Any]:
		"""Query all elements - REQUIRED for multiple element operations
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.querySelectorAll",
			"params": {
				"window_id": "window-123",
				"selector": ".my-class"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.querySelectorAll':
			const window = getWindow(params.window_id);
			const count = await window.webContents.executeJavaScript(`
				document.querySelectorAll('${params.selector}').length
			`);
			const elements = [];
			for (let i = 0; i < count; i++) {
				elements.push({ selector: params.selector, index: i });
			}
			return { elements };
		```
		"""
		result = await self._send_command('page.querySelectorAll', {
			'window_id': self.window_id,
			'selector': selector
		})
		return result.get('elements', [])
	
	def locator(self, selector: str, options: Optional[Dict[str, Any]] = None) -> 'ElectronLocator':
		"""Create locator - REQUIRED for tests and examples
		
		Returns a locator object that can be used for element interactions.
		"""
		return ElectronLocator(self, selector, options)
	
	# ===== Context Property (REQUIRED) =====
	
	@property
	def context(self) -> 'ElectronBrowserContextStub':
		"""Get browser context - REQUIRED for CDP session access
		
		Returns a minimal stub that supports new_cdp_session for compatibility.
		"""
		if not hasattr(self, '_context_stub'):
			self._context_stub = ElectronBrowserContextStub(self._session)
		return self._context_stub
	
	# ===== Event Methods (REQUIRED for network monitoring) =====
	
	def on(self, event: str, handler: Callable) -> None:
		"""Add event listener - REQUIRED for network request monitoring
		
		Example WebSocket message:
		{
			"id": "uuid-here", 
			"method": "page.addEventListener",
			"params": {
				"window_id": "window-123",
				"event": "request"
			}
		}
		
		Electron implementation:
		```javascript
		case 'page.addEventListener':
			const window = getWindow(params.window_id);
			// Register that this window wants to receive events
			registerEventListener(params.window_id, params.event);
			return { success: true };
		```
		"""
		if not hasattr(self, '_event_listeners'):
			self._event_listeners = {}
		
		if event not in self._event_listeners:
			self._event_listeners[event] = []
		
		self._event_listeners[event].append(handler)
		
		# Register with Electron if first listener
		if len(self._event_listeners[event]) == 1:
			asyncio.create_task(self._send_command('page.addEventListener', {
				'window_id': self.window_id,
				'event': event
			}))
	
	def remove_listener(self, event: str, handler: Callable) -> None:
		"""Remove event listener - REQUIRED for cleanup
		
		Example WebSocket message:
		{
			"id": "uuid-here",
			"method": "page.removeEventListener", 
			"params": {
				"window_id": "window-123",
				"event": "request"
			}
		}
		"""
		if hasattr(self, '_event_listeners') and event in self._event_listeners:
			try:
				self._event_listeners[event].remove(handler)
				
				# Unregister with Electron if no more listeners
				if not self._event_listeners[event]:
					asyncio.create_task(self._send_command('page.removeEventListener', {
						'window_id': self.window_id,
						'event': event
					}))
			except ValueError:
				pass
	
	# ===== Element Interaction Methods (used by locator) =====
	
	async def click(self, selector: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Click element - REQUIRED by locator"""
		await self._send_command('page.click', {
			'window_id': self.window_id,
			'selector': selector,
			'options': options or {}
		})
	
	async def fill(self, selector: str, value: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Fill input field - REQUIRED by locator"""
		await self._send_command('page.fill', {
			'window_id': self.window_id,
			'selector': selector,
			'value': value,
			'options': options or {}
		})
	
	async def type(self, selector: str, text: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Type text - REQUIRED by locator"""
		await self._send_command('page.type', {
			'window_id': self.window_id,
			'selector': selector,
			'text': text,
			'options': options or {}
		})
	
	async def press(self, selector: str, key: str, options: Optional[Dict[str, Any]] = None) -> None:
		"""Press key - REQUIRED by locator"""
		await self._send_command('page.press', {
			'window_id': self.window_id,
			'selector': selector,
			'key': key,
			'options': options or {}
		})
	
	async def inner_text(self, selector: str, options: Optional[Dict[str, Any]] = None) -> str:
		"""Get inner text - REQUIRED by locator"""
		result = await self._send_command('page.innerText', {
			'window_id': self.window_id,
			'selector': selector,
			'options': options or {}
		})
		return result.get('text', '')
	
	async def is_visible(self, selector: str, options: Optional[Dict[str, Any]] = None) -> bool:
		"""Check visibility - REQUIRED by locator"""
		result = await self._send_command('page.isVisible', {
			'window_id': self.window_id,
			'selector': selector,
			'options': options or {}
		})
		return result.get('visible', False)
	
	# ===== Stub Methods for Everything Else =====
	
	def __getattr__(self, name: str) -> Any:
		"""Catch-all for unimplemented methods
		
		This logs a warning and returns a no-op function for any 
		Playwright Page method we haven't implemented.
		"""
		logger.warning(f"ElectronPageProxy.{name}() not implemented - returning stub")
		
		# Return async or sync no-op based on common patterns
		if name.startswith('wait_') or name in ['hover', 'focus', 'check', 'uncheck',
												  'select_option', 'dispatch_event', 'pdf']:
			# Return async no-op
			async def async_stub(*args, **kwargs):
				logger.debug(f"STUB: {name}({args}, {kwargs})")
				return None
			return async_stub
		else:
			# Return sync no-op
			def sync_stub(*args, **kwargs):
				logger.debug(f"STUB: {name}({args}, {kwargs})")
				return None
			return sync_stub