"""
Simple test script to verify Electron WebSocket connections.
Run this to test if the ElectronSession and ElectronUIBridge can connect properly.
"""

import asyncio
import os

# Enable Electron backend
os.environ['USE_ELECTRON_BACKEND'] = 'true'

from browser_use.browser import BrowserSession  # This will be ElectronSession
from browser_use.electron import ElectronUIBridge


async def test_browser_connection():
	"""Test connection to browser control WebSocket"""
	print("Testing browser control connection on port 9222...")
	
	try:
		session = BrowserSession()
		await session.start()
		print("✓ Successfully connected to browser control")
		
		# Test ping command
		await session._send_command('ping', {})
		print("✓ Ping command successful")
		
		# Test navigation
		page = await session.navigate("https://example.com")
		print(f"✓ Navigation successful: {page.url}")
		
		# Test screenshot
		screenshot = await session.take_screenshot()
		if screenshot:
			print("✓ Screenshot captured")
		else:
			print("✗ Screenshot failed")
			
		await session.stop()
		print("✓ Session closed successfully")
		
	except Exception as e:
		print(f"✗ Browser control test failed: {e}")


async def test_ui_connection():
	"""Test connection to UI bridge WebSocket"""
	print("\nTesting UI bridge connection on port 9223...")
	
	try:
		ui_bridge = ElectronUIBridge()
		await ui_bridge.connect()
		print("✓ Successfully connected to UI bridge")
		
		# Test notification
		await ui_bridge.send_notification(
			"Test Notification",
			"This is a test notification from browser-use",
			"info"
		)
		print("✓ Notification sent")
		
		# Test user input (with timeout)
		print("Testing user input dialog...")
		try:
			response = await asyncio.wait_for(
				ui_bridge.request_user_input(
					"This is a test input dialog. Please enter something:",
					options=["Option 1", "Option 2", "Cancel"]
				),
				timeout=30
			)
			print(f"✓ User responded: {response}")
		except asyncio.TimeoutError:
			print("✗ User input timed out (no response in 30 seconds)")
			
		await ui_bridge.disconnect()
		print("✓ UI bridge closed successfully")
		
	except Exception as e:
		print(f"✗ UI bridge test failed: {e}")


async def main():
	"""Run all tests"""
	print("=== Electron Integration Test ===\n")
	
	print("Prerequisites:")
	print("1. Autai Electron app must be running")
	print("2. WebSocket servers must be listening on ports 9222 and 9223")
	print("3. USE_ELECTRON_BACKEND environment variable is set to 'true'\n")
	
	await test_browser_connection()
	await test_ui_connection()
	
	print("\n=== Test Complete ===")


if __name__ == "__main__":
	asyncio.run(main())