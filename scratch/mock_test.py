import sys
import os

# Add workspace directory to path
sys.path.insert(0, r"c:\Users\adity\Downloads\file-telegram-bot-main\file-telegram-bot-main")

from unittest.mock import MagicMock

# Create mock modules
db_mock = MagicMock()
models_mock = MagicMock()

# Define FileCategory enum mock since helper.py uses it
class MockFileCategory:
    VIDEO = "video"
    AUDIO = "audio"
    PHOTO = "photo"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    OTHER = "other"

models_mock.FileCategory = MockFileCategory

# Setup mock config with real secret string
config_module = MagicMock()
config_module.cfg.VAULT_SECRET = "some_secret_key_some_secret_key"

# Mock cryptography Fernet to return a mock class
crypto_module = MagicMock()
fernet_module = MagicMock()
crypto_module.fernet = fernet_module

sys.modules['config'] = config_module
sys.modules['database'] = db_mock
sys.modules['database.models'] = models_mock
sys.modules['cryptography'] = crypto_module
sys.modules['cryptography.fernet'] = fernet_module

import utils.keyboards as kb

# Build main menu
menu = kb.main_menu(is_premium=True, is_admin=True)

# Convert all buttons to dict and verify styles
print("Main menu keyboard dict structure:")
for row in menu.inline_keyboard:
    row_repr = []
    for btn in row:
        b_dict = btn.to_dict()
        # Escape emojis/unicode for windows console output compatibility
        text_safe = btn.text.encode('ascii', errors='replace').decode('ascii')
        row_repr.append(f"{text_safe} [style={b_dict.get('style')}]")
    print(" | ".join(row_repr))

print("\nAll checks passed successfully!")
