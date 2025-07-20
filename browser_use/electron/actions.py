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