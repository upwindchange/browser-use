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