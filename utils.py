import os
import sys
import subprocess
import pkg_resources
from dotenv import load_dotenv

# --- CONFIGURATION ---
# You keep your key in GEMINI_API_KEY, we map it to what DroidRun needs
SOURCE_KEY_ENV = "GOOGLE_API_KEY" 
DROIDRUN_EXPECTED_ENV = "GOOGLE_API_KEY"

# Model from your request
DEFAULT_MODEL = "gemini-3-flash-preview" 
PROVIDER_NAME = "GoogleGenAI" # As per DroidRun Docs
TEMPERATURE = 0

def setup_gemini_env():
    """
    Loads environment variables and configures DroidRun for Native Gemini.
    """
    load_dotenv()
    
    api_key = os.getenv(SOURCE_KEY_ENV)
    if not api_key:
        print(f" Error: {SOURCE_KEY_ENV} not found in .env file.")
        print(f"   Please add {SOURCE_KEY_ENV}=your_key_here to your .env file.")
        sys.exit(1)
    
    # DroidRun's GoogleGenAI provider looks for GOOGLE_API_KEY
    os.environ[DROIDRUN_EXPECTED_ENV] = api_key
    
    # Check if the google extra is installed
    _check_google_dependencies()
    
    print(f"Using: {DEFAULT_MODEL}")
    
    # Generate the config.yaml for DroidAgent
    _write_config_file()
    
    return {"model": DEFAULT_MODEL}

def _check_google_dependencies():
    """Checks if droidrun[google] dependencies are present."""
    try:
        # Just a basic check to see if we can import the underlying library
        import google.generativeai
    except ImportError:
        print(" WARNING: Google GenAI dependencies not found.")
        print("   Please run: pip install 'droidrun[google]'")
        print("   Or: pip install google-generativeai llama-index-llms-gemini")

def _write_config_file():
    """
    Generates a config.yaml that forces DroidRun to use the Native GoogleGenAI provider.
    """
    # This structure mirrors the native provider setup
    content = f"""agent:
  vision: true
  reasoning: true
  max_steps: 20

llm_profiles:
  default:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

  manager:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

  executor:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

  codeact:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

  text_manipulator:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

  app_opener:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

      scripter:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: {TEMPERATURE}

  structured_output:
    provider: {PROVIDER_NAME}
    model: {DEFAULT_MODEL}
    temperature: 0.0
"""
    with open("config.yaml", "w") as f:
        f.write(content)
