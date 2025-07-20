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
from browser_use.dom.views import DOMElementNode, SelectorMap

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
		current_page = await self.get_current_page()
		if not current_page:
			return BrowserStateSummary(
				url="",
				title="No page",
				tabs=[],
				dom_tree=DOMElementNode(tag="html", attributes={}, children=[]),
				selector_map=SelectorMap()
			)
			
		# Get DOM tree from Electron
		try:
			dom_result = await self._send_command('get_dom_tree', {
				'window_id': current_page.window_id
			})
			dom_tree = DOMElementNode(**dom_result.get('dom_tree', {}))
			selector_map = SelectorMap(**dom_result.get('selector_map', {}))
		except:
			dom_tree = DOMElementNode(tag="html", attributes={}, children=[])
			selector_map = SelectorMap()
		
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
			selector_map=selector_map,
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