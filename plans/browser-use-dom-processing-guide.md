# Browser-Use DOM Processing and Agent Context Discovery Guide

## Table of Contents
1. [Overview](#overview)
2. [DOM Processing Architecture](#dom-processing-architecture)
3. [What the Agent Sees](#what-the-agent-sees)
4. [Core Components](#core-components)
5. [Interactive Element Detection](#interactive-element-detection)
6. [DOM State Management](#dom-state-management)
7. [Advanced Features](#advanced-features)
8. [Performance Optimizations](#performance-optimizations)

## Overview

Browser-Use is an async Python library (>=3.11) that enables AI agents to interact with web browsers using LLMs and Playwright. The DOM processing system is a critical component that transforms complex web pages into a simplified, hierarchical representation that LLMs can understand and interact with.

### Key Design Principles
- **Selective Processing**: Only interactive elements and their context are presented to the agent
- **Hierarchical Preservation**: Parent-child relationships are maintained through indentation
- **Token Efficiency**: Smart filtering and truncation to optimize LLM token usage
- **State Tracking**: Intelligent detection of new elements across page updates

## DOM Processing Architecture

### Three-Phase Processing Pipeline

1. **JavaScript Extraction Phase** (Browser)
   - Injects JavaScript code (`dom_tree/index.js`) into the page
   - Identifies interactive elements based on comprehensive criteria
   - Assigns numeric indices (`highlightIndex`) to interactive elements
   - Returns flat data structure to Python

2. **Python Construction Phase**
   - Receives flat JavaScript data structure
   - Builds tree of `DOMElementNode` and `DOMTextNode` objects
   - Establishes parent-child relationships
   - Creates selector map for quick element lookup

3. **String Generation Phase**
   - Converts DOM tree to indented string format
   - Includes only elements with `highlightIndex`
   - Adds context (text content, attributes)
   - Preserves hierarchy through tab indentation

## What the Agent Sees

### DOM String Format
The agent receives a simplified, hierarchical representation:

```
Current tab: 0
Available tabs:
Tab 0: https://example.com - Example Store
Tab 1: https://other.com - Other Site

Page info: [viewport: 1920x1080, scroll: 0x0]
Interactive elements from top layer of the current page inside the viewport:
[Start of page]
[1]<h1>Welcome to Example Store</h1>
[2]<input type='search' placeholder='Search products' />
[3]<button>Search</button>
Products:
[4]<div>iPhone 15</div>
    Latest smartphone from Apple
    Price: $999
    [5]<button>Add to Cart</button>
[6]<div>Samsung Galaxy S24</div>
    Android flagship phone
    Price: $899
    *[7]<button>Add to Cart</button>
[End of page]
```

### Format Explanation
- `[index]`: Interactive element with numeric ID for referencing
- `*[index]`: New element since last observation
- Indentation: Shows parent-child relationships
- Text without brackets: Non-interactive context
- Attributes: Only relevant ones shown (aria-label, placeholder, type, etc.)

## Core Components

### 1. DOMElementNode Class
```python
@dataclass(frozen=False)
class DOMElementNode(DOMBaseNode):
    tag_name: str                    # HTML tag (div, button, a, etc.)
    xpath: str                       # XPath from nearest root
    attributes: dict[str, str]       # HTML attributes
    children: list[DOMBaseNode]      # Child elements
    is_interactive: bool = False     # Can be interacted with
    is_top_element: bool = False     # Topmost at position
    is_in_viewport: bool = False     # Currently visible
    is_visible: bool                 # Rendered on page
    highlight_index: int | None = None  # Numeric ID for interaction
    is_new: bool | None = None       # New since last step
```

### 2. Key Methods

#### `get_all_text_till_next_clickable_element()`
Collects text content belonging to an interactive element:
```python
def get_all_text_till_next_clickable_element(self, max_depth: int = -1) -> str:
    # Recursively collect text from children
    # STOP when hitting another element with highlight_index
    # Prevents text duplication between interactive elements
```

#### `clickable_elements_to_string()`
Converts DOM tree to agent-readable format:
```python
def clickable_elements_to_string(self, include_attributes: list[str] | None = None) -> str:
    # Process only elements with highlight_index
    # Include their text content via get_all_text_till_next_clickable_element()
    # Add non-interactive text nodes for context
    # Preserve hierarchy through indentation
```

## Interactive Element Detection

### JavaScript Detection Criteria

An element is considered interactive if it meets ANY of these criteria:

1. **Interactive Cursor Styles**
   ```javascript
   ['pointer', 'move', 'text', 'grab', 'cell', 'copy', ...]
   ```

2. **Interactive HTML Tags**
   ```javascript
   ['a', 'button', 'input', 'select', 'textarea', 'details', 'summary', ...]
   ```

3. **ARIA Roles**
   ```javascript
   ['button', 'checkbox', 'radio', 'tab', 'switch', 'slider', ...]
   ```

4. **Content Editable**
   - `contenteditable="true"`
   - `isContentEditable` property

5. **Event Listeners**
   - onclick, onmousedown, onkeydown, onchange, etc.

6. **Class/Attribute Indicators**
   - Classes: `button`, `dropdown-toggle`
   - Attributes: `data-toggle="dropdown"`, `aria-haspopup="true"`

### Exclusion Criteria

Elements are NOT interactive if they have:
- `disabled` attribute or property
- `readonly` attribute or property
- `inert` property
- Non-interactive cursors: `not-allowed`, `no-drop`, `wait`

### highlightIndex Assignment

Not all interactive elements get a `highlightIndex`. Requirements:

1. **Must be interactive** (`isInteractive: true`)
2. **Must be visible** (`isVisible: true`)
3. **Must be topmost** (`isTopElement: true`)
4. **Must be in viewport** (`isInViewport: true`) OR `viewportExpansion: -1`
5. **Must be distinct** from parent interaction

## DOM State Management

### JavaScript to Python Data Transfer

JavaScript returns this structure:
```javascript
{
  rootId: "0",  // ID of root element (body)
  map: {
    "0": { 
      tagName: "body", 
      children: ["1", "2"], 
      xpath: ""
    },
    "1": { 
      tagName: "button",
      attributes: { onclick: "...", class: "btn" },
      xpath: "div[1]/button[1]",
      children: ["3"],
      isInteractive: true,
      isVisible: true,
      isTopElement: true,
      isInViewport: true,
      highlightIndex: 0
    },
    "3": { 
      type: "TEXT_NODE", 
      text: "Click me", 
      isVisible: true 
    }
  }
}
```

### New Element Detection

1. **Hashing System**
   ```python
   hash = SHA256(branch_path_hash + attributes_hash + xpath_hash)
   ```
   - Branch path: Element's path from root (e.g., `html/body/div/button`)
   - Attributes: All attributes concatenated
   - XPath: Element's position

2. **Cache Comparison**
   - Previous state hashes stored in cache
   - New elements compared against cache
   - Hash not in cache → `is_new = true` (marked with `*`)

3. **Cache Scope**
   - URL-specific (cleared on navigation)
   - Tab-specific (cleared on tab switch)
   - Only tracks clickable elements (performance)

### Visibility Properties

1. **`isVisible`**: Element is rendered
   - Has dimensions (`offsetWidth > 0`, `offsetHeight > 0`)
   - Not hidden by CSS (`display !== "none"`, `visibility !== "hidden"`)
   - Can be true even if scrolled off-screen

2. **`isInViewport`**: Element is in viewing area
   - Within viewport bounds + `viewportExpansion` margin
   - Only checked if `isVisible: true`
   - Required for `highlightIndex` assignment

## Advanced Features

### 1. Viewport Expansion
```python
# Default: 500px margin in all directions
BrowserProfile(viewport_expansion=500)

# Tight viewport (visible only)
BrowserProfile(viewport_expansion=0)

# Full page mode (all elements)
BrowserProfile(viewport_expansion=-1)
```

### 2. Shadow DOM and iFrame Handling
- XPaths are relative to nearest root (shadow root, iframe, or document)
- Cross-origin iframes listed separately
- Agent must switch contexts for interaction

### 3. Multi-Tab Context
```
Available tabs:
Tab 0: https://site1.com - Title 1
Tab 1: https://site2.com - Title 2
Current tab: 0
```

### 4. Scroll Position Indicators
```
[... 250 pixels above - scroll to see more ...]
<visible content>
[... 1500 pixels below - scroll to see more ...]
```

### 5. DOM Truncation
- Default limit: 40,000 characters
- Prevents token overflow
- Configurable via settings

### 6. Text Node Context
- Shows non-interactive text for context
- Only if parent is visible and top element
- Provides prices, descriptions, labels

### 7. Attribute Filtering
Smart filtering to reduce noise:
- Removes duplicate text attributes
- Removes role if matches tag name
- Caps values at 15 characters
- Only includes from `DEFAULT_INCLUDE_ATTRIBUTES`:
  ```python
  ['title', 'type', 'checked', 'name', 'role', 'value', 
   'placeholder', 'alt', 'aria-label', 'aria-expanded', ...]
  ```

## Performance Optimizations

1. **JavaScript Caching**
   - Caches bounding rects, computed styles, client rects
   - Reuses calculations across elements

2. **Selective Processing**
   - Only processes visible, interactive elements
   - Skips hidden or disabled elements early

3. **Efficient Data Transfer**
   - Flat hash map structure (not nested)
   - ID references instead of embedded children

4. **State Persistence**
   - Reuses element hashes across steps
   - Maintains cache per URL/tab

5. **Batch Operations**
   - Processes all elements in single JavaScript execution
   - Builds Python tree in single pass

## Usage Examples

### Basic Configuration
```python
from browser_use import Agent, BrowserSession, BrowserProfile
from browser_use.llm import ChatOpenAI

# Standard usage (500px viewport expansion)
agent = Agent(
    task="Find and click the Add to Cart button",
    llm=ChatOpenAI(model="gpt-4o"),
)

# Full page analysis
browser_session = BrowserSession(
    browser_profile=BrowserProfile(viewport_expansion=-1)
)

# Minimal token usage
browser_session = BrowserSession(
    browser_profile=BrowserProfile(viewport_expansion=0)
)
```

### Accessing DOM State
```python
# Get current DOM state
state = await browser_session.get_state_summary()
dom_string = state.element_tree.clickable_elements_to_string()

# Check for new elements
if element.is_new:
    print(f"New element detected: {element.tag_name}")
```

## Best Practices

1. **Token Management**
   - Use default `viewport_expansion=500` for most tasks
   - Use `-1` only when full page context is essential
   - Monitor DOM string length for token usage

2. **Element Interaction**
   - Always use numeric indices from brackets
   - Check `is_new` flag for dynamic content
   - Consider scroll indicators for navigation

3. **State Tracking**
   - Rely on `is_new` markers for changes
   - Understand viewport vs visibility distinction
   - Use multi-tab context for complex workflows

4. **Performance**
   - Minimize viewport expansion for faster processing
   - Batch similar operations
   - Reuse browser sessions when possible

This comprehensive system enables AI agents to understand and interact with complex web pages efficiently while maintaining the context necessary for intelligent decision-making.