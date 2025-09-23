from pydantic import BaseModel, Field
from types import SimpleNamespace
from typing import List, Dict, Any, Optional, Type, TypeVar
import os
import json

# Generic type for load_json_config (defined after imports)
M = TypeVar('M', bound=BaseModel)

# Prefer the external pydantic-settings package (pydantic v2 separation).
# If it's not available, we'll provide a lightweight fallback so the
# repository can be imported in environments without pydantic-settings.
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAVE_PYDANTIC_SETTINGS = True
except Exception:
    HAVE_PYDANTIC_SETTINGS = False
    BaseSettings = None
    SettingsConfigDict = dict

class PlaywrightConfig(BaseModel):
    user_data_dir: str = Field(..., alias='userDataDir')
    whatsapp_url: str = Field(..., alias='whatsappUrl')
    headless: bool = False
    message_check_interval: float = Field(..., alias='messageCheckInterval')
    max_retries: int = Field(..., alias='maxRetries')
    navigation_timeout: int = Field(..., alias='navigationTimeout')

class ReasonerMessage(BaseModel):
    role: str
    content: str

class ReasonerPayload(BaseModel):
    model: str
    temperature: float
    max_tokens: int
    messages: List[ReasonerMessage]

class PromptsConfig(BaseModel): # ADDED THIS CLASS
    conversational: str = 'Responde de forma útil y breve.'
    reasoner: str = 'Piensa paso a paso antes de responder.'
    conversation: str = ''

# --- Start: Manual JSON config loader ---
def load_json_config(path: str, model: Type[M], default: Dict) -> M:
    """Load a JSON file into a Pydantic model, with a fallback to a default dict."""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # --- NEW: Expand environment variables and coerce common types ---
            import re
            expanded_data = {}
            placeholder_re = re.compile(r'^\$\{([A-Za-z0-9_]+)\}$')

            for key, value in data.items():
                # Expand environment variable references like ${VAR}
                if isinstance(value, str):
                    # First expand any $VAR or ${VAR} forms where env var exists
                    v = os.path.expandvars(value)

                    # If it is a single placeholder like ${FOO} and not set, try to use env directly
                    m = placeholder_re.match(v)
                    if m:
                        envname = m.group(1)
                        envval = os.getenv(envname)
                        if envval is not None:
                            v = envval

                    # Coerce booleans encoded as strings
                    if isinstance(v, str) and v.lower() in ("true", "false"):
                        expanded_val = v.lower() == "true"
                    else:
                        expanded_val = v

                    # Try to coerce numeric-ish strings to int/float where sensible
                    if isinstance(expanded_val, str):
                        s = expanded_val.strip()
                        # Integer-like
                        if s.isdigit():
                            try:
                                expanded_val = int(s)
                            except Exception:
                                pass
                        else:
                            # Float-like (e.g. '5.0')
                            try:
                                if any(ch in s for ch in '.eE'):
                                    expanded_val = float(s)
                                else:
                                    # Try int conversion as last resort
                                    expanded_val = int(s)
                            except Exception:
                                # leave as string if it cannot be cast
                                pass

                    expanded_data[key] = expanded_val
                else:
                    expanded_data[key] = value
            # --- END NEW ---

            # Attempt to instantiate the Pydantic model; on any validation error
            # fall back to the provided default to avoid raising during import.
            try:
                return model(**expanded_data)
            except Exception:
                return model(**default)
        except Exception:
            # Fallback on any read/parse error
            return model(**default)
    return model(**default)
# --- End: Manual JSON config loader ---


def _make_fallback():
    # Lightweight fallback: construct a SimpleNamespace with the same keys,
    # reading environment variables (UPPER_SNAKE_CASE) when present.
    def _env(key: str, default, cast=None):
        name = key.upper()
        val = os.getenv(name)
        if val is None:
            return default
        if cast is None:
            return val
        try:
            if cast is bool:
                return val.lower() in ("1", "true", "yes", "on")
            return cast(val)
        except Exception:
            return default

    _defaults = {
        'admin_base': "http://127.0.0.1:8014",
        'lm_studio_port': 1234,
        'database_url': None,
        'use_dev_frontend': False,
        'open_browser': True,
        'fernet_key': None,
        'uvicorn_port': 8014,
        'frontend_port': 3000,
        'reasoner_payload_path': "payload_reasoner.json",
        'playwright_profile_dir': "./data/whatsapp-profile",
        'whatsapp_url': "https://web.whatsapp.com/",
        'typing_per_char': 0.05,
        'automator_cooldown_minutes': 2,
        'log_path': "./logs/automation.log",
        'keep_automator_open': False,
        'automation_active': True,
        'strategy_refresh_every': 10,
        'require_contact_profile': True,
        'respond_to_all': False,
    }

    # Top-level simple keys
    fallback = {k: _env(k, v, cast=(int if isinstance(v, int) else (float if isinstance(v, float) else (bool if isinstance(v, bool) else None)))) for k, v in _defaults.items()}

    # Build a nested `playwright` namespace expected by the rest of the code
    pw_user_dir = os.path.expandvars(str(os.getenv('PLAYWRIGHT_USER_DATA_DIR', fallback.get('playwright_profile_dir'))))
    pw_whatsapp_url = os.path.expandvars(str(os.getenv('PLAYWRIGHT_WHATSAPP_URL', fallback.get('whatsapp_url'))))
    try:
        pw_message_interval = float(str(os.getenv('PLAYWRIGHT_MESSAGE_CHECK_INTERVAL', fallback.get('automator_cooldown_minutes', 5))))
    except Exception:
        pw_message_interval = float(fallback.get('automator_cooldown_minutes', 5))

    playwright_ns = SimpleNamespace(
        user_data_dir=pw_user_dir,
        whatsapp_url=pw_whatsapp_url,
        headless=(os.getenv('PLAYWRIGHT_HEADLESS', 'false').lower() in ('1', 'true', 'yes', 'on')),
        message_check_interval=pw_message_interval,
        max_retries=int(os.getenv('PLAYWRIGHT_MAX_RETRIES', 3)),
        navigation_timeout=int(os.getenv('PLAYWRIGHT_NAVIGATION_TIMEOUT', 30000)),
    )

    fallback['playwright'] = playwright_ns
    # Add constants for status monitor with simple defaults
    fallback.update({
        'STATUS_CHECK_INTERVAL_SECONDS': int(_env('STATUS_CHECK_INTERVAL_SECONDS', 30, int)),
        'STATUS_MAX_TREND_POINTS': int(_env('STATUS_MAX_TREND_POINTS', 20, int)),
        'DEFAULT_SERVICE_TIMEOUT_MS': int(_env('DEFAULT_SERVICE_TIMEOUT_MS', 10000, int)),
        'DEFAULT_EXPECTED_LATENCY_MS': int(_env('DEFAULT_EXPECTED_LATENCY_MS', 10000, int)),
    })

    return SimpleNamespace(**fallback)


if HAVE_PYDANTIC_SETTINGS and BaseSettings is not None:
    # Default dictionaries for fallback
    DEFAULT_PLAYWRIGHT = {
        "userDataDir": "./data/whatsapp-profile",
        "whatsappUrl": "https://web.whatsapp.com/",
        "headless": False,
        "messageCheckInterval": 5,
        "maxRetries": 3,
        "navigationTimeout": 30000
    }
    DEFAULT_REASONER = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 1000,
        "messages": [{"role": "system", "content": "You are a helpful assistant."}]
    }

    class Settings(BaseSettings):
        # Environment variables
        admin_base: str = "http://127.0.0.1:8014"
        lm_studio_api_key: str = "lm-studio"
        lm_studio_port: int = 1234
        database_url: Optional[str] = None
        use_dev_frontend: bool = False
        open_browser: bool = True
        fernet_key: Optional[str] = None
        uvicorn_port: int = 8014
        frontend_port: int = 3000
        reasoner_payload_path: str = "payload_reasoner.json"
        playwright_profile_dir: str = "./data/whatsapp-profile"
        whatsapp_url: str = "https://web.whatsapp.com/"
        typing_per_char: float = 0.05
        log_path: str = "./logs/automation.log"
        keep_automator_open: bool = True
        automation_active: bool = True
        strategy_refresh_every: int = 10
        require_contact_profile: bool = True  # Moved here from whatsapp_automator.py
        # Automator specific
        respond_to_all: bool = False
        automator_cooldown_minutes: float = 2.0  # minutes used to avoid reply loops

        # NEW: Add whatsapp_contacts_file and whatsapp_contacts_file_backup
        whatsapp_contacts_file: str = "./data/contacts.json"
        whatsapp_contacts_file_backup: str = "./data/contacts_backup.json"

        # NEW: Add LM Studio related settings
        lm_studio_url: str = "http://127.0.0.1:1234/v1/chat/completions"
        default_model: str = "nemotron-mini-4b-instruct"
        lms_exe: Optional[str] = None # Make optional as it might not always be present
        lm_studio_dir: Optional[str] = None # Make optional

        # Status Monitor Settings
        STATUS_CHECK_INTERVAL_SECONDS: int = 30
        STATUS_MAX_TREND_POINTS: int = 20
        DEFAULT_SERVICE_TIMEOUT_MS: int = 10000
        DEFAULT_EXPECTED_LATENCY_MS: int = 10000
        STATUS_MONITOR_SERVICES: List[Dict[str, Any]] = [
            {
                'name': 'openai',
                'display_name': 'OpenAI GPT',
                'priority': 1,
                'expected_latency_ms': 1500,
                'timeout_ms': 10000
            },
            {
                'name': 'claude',
                'display_name': 'Anthropic Claude',
                'priority': 2,
                'expected_latency_ms': 2000,
                'timeout_ms': 15000
            },
            {
                'name': 'gemini',
                'display_name': 'Google Gemini',
                'priority': 3,
                'expected_latency_ms': 1800,
                'timeout_ms': 12000
            },
            {
                'name': 'xai',
                'display_name': 'X.AI Grok',
                'priority': 4,
                'expected_latency_ms': 3000,
                'timeout_ms': 20000
            },
            {
                'name': 'ollama',
                'display_name': 'Ollama Local',
                'priority': 5,
                'expected_latency_ms': 500,
                'timeout_ms': 5000
            }
        ]

        # Manually loaded JSON file configurations
        playwright: PlaywrightConfig = Field(default_factory=lambda: load_json_config('config/playwright_config.json', PlaywrightConfig, DEFAULT_PLAYWRIGHT))
        reasoner: ReasonerPayload = Field(default_factory=lambda: load_json_config('payload_reasoner.json', ReasonerPayload, DEFAULT_REASONER))
        prompts: PromptsConfig = PromptsConfig()  # Uses default values
        api_keys: Dict[str, str] = Field(default_factory=dict)  # API keys for online models

        # Configure settings sources if pydantic-settings is available
        if HAVE_PYDANTIC_SETTINGS:
            model_config = SettingsConfigDict(  # type: ignore
                env_file=".env",
                env_file_encoding="utf-8",
                extra='ignore'
            )
        else:
            model_config = {}

    # Instantiate Settings, but be forgiving: if instantiation fails for any
    # reason (validation errors, missing env vars, etc.) fall back to the
    # lightweight SimpleNamespace so the app can still start and the user can
    # inspect/repair configuration.
    try:
        settings = Settings()
    except Exception:
        settings = _make_fallback()
else:
    # pydantic-settings not available - use fallback simple namespace
    settings = _make_fallback()
