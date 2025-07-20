"""
Example of using browser-use with Electron backend integration.

This example demonstrates:
1. Using ElectronSession instead of Playwright
2. Human-in-the-loop interactions with custom actions
3. Real-time event streaming to UI

Prerequisites:
- Set environment variable: USE_ELECTRON_BACKEND=true
- Ensure Autai Electron app is running with WebSocket servers on ports 9222 and 9223
"""

import asyncio
import os

# Enable Electron backend
os.environ['USE_ELECTRON_BACKEND'] = 'true'

from browser_use import Agent
from browser_use.controller import Controller
from browser_use.llm.openai import ChatOpenAI
from browser_use.electron import ElectronUIBridge
from browser_use.electron import actions


async def main():
	"""Main example function demonstrating Electron integration"""
	
	# Initialize UI bridge
	ui_bridge = ElectronUIBridge()
	await ui_bridge.connect()
	print("Connected to Electron UI")
	
	# Set up UI bridge for actions
	actions.ui_bridge = ui_bridge
	
	# Create controller with Electron-specific actions
	controller = Controller()
	
	# Register human-in-the-loop actions
	controller.action("Ask user for input", param_model=actions.AskUserParams)(actions.ask_user_electron)
	controller.action("Confirm action with user", param_model=actions.ConfirmActionParams)(actions.confirm_action_electron)
	controller.action("Let user select option", param_model=actions.SelectOptionParams)(actions.select_option_electron)
	controller.action("Notify user", param_model=actions.NotifyUserParams)(actions.notify_user_electron)
	
	# Create agent with Electron backend
	# The BrowserSession will automatically be ElectronSession due to environment variable
	agent = Agent(
		task="Help me search for Python tutorials. Ask me what specific topic I'm interested in before searching.",
		llm=ChatOpenAI(model="gpt-4"),
		controller=controller
	)
	
	# Subscribe UI to agent events for real-time updates
	ui_bridge.subscribe_to_agent_events(agent)
	
	# Set up UI command handlers
	async def handle_pause():
		print("Agent paused by user")
		# Implement pause logic here
		
	async def handle_resume():
		print("Agent resumed by user")
		# Implement resume logic here
		
	async def handle_stop():
		print("Agent stopped by user")
		# Implement stop logic here
		
	# Register command handlers
	ui_bridge.event_bus.on('ui_command_pause', lambda _: asyncio.create_task(handle_pause()))
	ui_bridge.event_bus.on('ui_command_resume', lambda _: asyncio.create_task(handle_resume()))
	ui_bridge.event_bus.on('ui_command_stop', lambda _: asyncio.create_task(handle_stop()))
	
	try:
		# Run the agent
		print("Starting agent...")
		result = await agent.run()
		print(f"Task completed: {result}")
		
	except KeyboardInterrupt:
		print("\nInterrupted by user")
		
	finally:
		# Cleanup
		await ui_bridge.disconnect()
		print("Disconnected from Electron UI")


if __name__ == "__main__":
	# Run the example
	asyncio.run(main())