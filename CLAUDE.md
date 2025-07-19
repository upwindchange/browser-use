# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Browser-Use is an async Python >= 3.11 library that implements AI browser driver abilities using LLMs + Playwright.
We want our library APIs to be ergonomic, intuitive, and hard to get wrong.

## Development Commands

### Environment Setup
```bash
# Use uv (ALWAYS prefer uv over pip)
uv venv --python 3.11
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv sync

# Install browser (required)
playwright install chromium --with-deps --no-shell

# Install with optional dependencies
uv sync --all-extras  # or specific extras like --extra cli,aws,examples
```

### Development Workflow
```bash
# Run linting, formatting, and type checking (ALWAYS run before commits)
uv run pre-commit run --all-files
# Or use the shortcut script:
./bin/lint.sh

# Run tests
uv run pytest -vxs tests/ci  # Run all CI tests
uv run pytest -vxs tests/ci -k "test_name"  # Run specific test
uv run pytest --numprocesses auto tests/ci  # Run tests in parallel
# Or use the shortcut script:
./bin/test.sh

# Type checking only
uv run pyright

# Run specific ruff checks
uv run ruff check browser_use/
uv run ruff format browser_use/
```

### CLI Usage
```bash
# Install CLI dependencies
uv sync --extra cli

# Run the interactive CLI
browser-use  # or browseruse
```

## High-Level Architecture

### Core Components

1. **Agent** (`browser_use/agent/service.py`)
   - Main orchestrator that processes tasks using an LLM
   - Manages conversation history, state tracking, and action execution
   - Uses MessageManager for prompt construction and history management
   - Integrates with Controller for action execution

2. **Controller** (`browser_use/controller/service.py`)
   - Manages action registry and execution
   - Default actions: search_google, go_to_url, click_element, input_text, scroll, etc.
   - Extensible via `@controller.registry.action()` decorator
   - Returns ActionResult with extracted content and memory flags

3. **Browser Session** (`browser_use/browser/session.py`)
   - Manages Playwright browser lifecycle
   - Handles tab management, navigation, and page state
   - Supports profiles, cookies, and extensions
   - Validates URLs against allowed_domains for security

4. **DOM Processing** (`browser_use/dom/`)
   - Extracts and processes page content for LLM consumption
   - HistoryTreeProcessor manages DOM state across interactions
   - Clickable element detection and interaction mapping
   - JavaScript injection for DOM tree extraction

5. **LLM Integration** (`browser_use/llm/`)
   - Supports multiple providers: OpenAI, Anthropic, Google, Azure, AWS, etc.
   - Each provider has chat.py and serializer.py
   - Base classes in `base.py` define the interface
   - Message types in `messages.py` and `schema.py`

6. **MCP Integration** (`browser_use/mcp/`)
   - Model Context Protocol support for tool integration
   - Can act as MCP server (for Claude Desktop)
   - Can connect to external MCP servers as client

## Code Style

- Use async Python throughout
- Use **tabs for indentation** in all Python code, not spaces
- Use modern Python >3.12 typing: `str | None` not `Optional[str]`, `list[str]` not `List[str]`
- Keep logging in separate `_log_*` methods to avoid cluttering main logic
- Use Pydantic v2 models for all data structures and API parameters
- Pydantic models should use `ConfigDict(extra='forbid', validate_by_name=True)`
- Main logic in `service.py`, Pydantic models in `views.py`
- Use runtime assertions to enforce constraints
- Use `uuid7str` for new ID fields: `id: str = Field(default_factory=uuid7str)`
- File/module structure follows a consistent pattern per component

## Testing Guidelines

- Tests go in `tests/ci/` for CI execution, `tests/old/` for legacy/WIP tests
- Never use mocks except for LLM responses
- Use pytest fixtures for setup, pytest-httpserver for web mocking
- Never use real URLs in tests - always mock with pytest-httpserver
- Modern pytest-asyncio: no `@pytest.mark.asyncio` needed, just use async functions
- Use `asyncio.get_event_loop()` inside tests if needed
- Simple `@pytest.fixture` decorator (no arguments) for all fixtures

## Making Changes

1. **Before changes**: Find/write tests verifying current behavior
2. **Write failing tests** for new behavior, confirm they fail
3. **Implement changes**, run tests during development
4. **Run full test suite**: `uv run pytest -vxs tests/ci`
5. **Consolidate tests**: Remove redundancy, ensure comprehensive coverage
6. **Update docs/examples** to match implementation

## Adding New Features

### New Browser Actions
```python
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult

controller = Controller()

@controller.registry.action("Description of what action does", param_model=YourParamModel)
async def your_action(params: YourParamModel, browser_session: BrowserSession):
    # Implementation
    return ActionResult(
        extracted_content="Result text",
        include_in_memory=True,
        long_term_memory="Summary for agent memory"
    )
```

### New LLM Provider
1. Create `browser_use/llm/yourprovider/chat.py` implementing `BaseChatModel`
2. Create `browser_use/llm/yourprovider/serializer.py` for message conversion
3. Add to `browser_use/llm/__init__.py` exports
4. Add tests in `browser_use/llm/tests/`

## Important Patterns

- **Event-driven architecture**: Uses bubus EventBus for decoupling
- **Telemetry/observability**: Built-in telemetry via ProductTelemetry
- **Cloud sync**: Optional cloud features via CloudSync
- **File system access**: Managed through FileSystem service
- **Security**: URL validation, sensitive data masking, action parameter sanitization

## Common Pitfalls

- Always use `browser_session.navigate_to()` not `page.goto()` for URL validation
- Run pre-commit hooks before committing
- Don't create example files when implementing features
- Keep system prompts in separate .md files
- Use ActionResult for all controller actions
- Handle both sync and async contexts appropriately

## Additional Context

- Main branch is for active development; use releases for production
- Discord community for questions and showcases
- Cloud version available at cloud.browser-use.com
- Documentation at docs.browser-use.com
- Never include sensitive data in code or commits