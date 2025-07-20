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
