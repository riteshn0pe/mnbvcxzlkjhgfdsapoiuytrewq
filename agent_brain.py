import traceback
import json
import os
import threading
from droidrun import DroidAgent, DroidrunConfig
from utils import setup_gemini_env

# --- MEMORY FILE PATH ---
MEMORY_FILE = "session_memory.json"

# --- [NEW] Natural Male Voice Helper (Edge-TTS) ---
def announce_action(text: str):
    def _speak():
        try:
            # Using Microsoft Guy (Neural) - A very natural male voice
            voice = "en-US-GuyNeural"
            filename = f"speech_{threading.get_ident()}.mp3"
            
            # Generate the natural voice file
            os.system(f'edge-tts --voice {voice} --text "{text}" --write-media {filename}')
            
            # Play and clean up
            if os.path.exists(filename):
                os.system(f"play -q {filename} > /dev/null 2>&1")
                os.remove(filename)
        except Exception as e:
            print(f"DEBUG Voice Error: {e}")

    threading.Thread(target=_speak, daemon=True).start()

# --- Custom Tools with Rich Descriptions (Kept Exactly as requested) ---
def save_note(key: str, value: str, **kwargs) -> str:
    try:
        data = {}
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'r') as f: 
                    data = json.load(f)
            except: 
                pass 
        data[key] = value
        with open(MEMORY_FILE, 'w') as f: 
            json.dump(data, f, indent=2)
        return f"✓ Saved to memory: {key} = {value}"
    except Exception as e: 
        return f"✗ Error saving: {e}"

def read_notes(**kwargs) -> str:
    try:
        if not os.path.exists(MEMORY_FILE): 
            return "Memory is empty. No data saved yet."
        with open(MEMORY_FILE, 'r') as f: 
            data = json.load(f)
        if not data:
            return "Memory is empty."
        return f"Memory Contents:\n{json.dumps(data, indent=2)}"
    except Exception as e: 
        return f"✗ Error reading: {e}"

CUSTOM_TOOLS = {
    "save_note": {
        "arguments": ["key", "value"], 
        "description": """Save information to persistent memory for later retrieval.

WHEN TO USE:
- Comparing multiple products/prices (save each one as you find it)
- Tracking search results across different screens
- Storing data that will be needed for final decision/comparison
- Recording details before moving to next step

USAGE EXAMPLES:
- save_note(key="jeans_product1", value="Roadster Baggy Jeans ₹1299 40% off")
- save_note(key="jeans_product2", value="Levi's Baggy ₹2499 20% off")
- save_note(key="best_price_found", value="₹899")

IMPORTANT: Use descriptive keys like "product1_price", "item_name", "best_deal" """,
        "function": save_note
    },
    "read_notes": {
        "arguments": [], 
        "description": """Retrieve ALL saved information from memory to view or compare.

WHEN TO USE:
- Before making final comparison between saved items
- When you need to recall previously saved prices/details
- At end of search to review all collected data
- To check what information was already saved

RETURNS: JSON object containing all key-value pairs from memory

EXAMPLE: After saving 3 products, call read_notes() to see all prices together for comparison""",
        "function": read_notes
    }
}

# --- Factory Function ---
def create_agent(
    goal_text: str, 
    app_card_instructions: str = None, 
    use_structured_output: bool = False,
    reasoning: bool = False,
    vision: bool = True
) -> DroidAgent:
    """
    Create DroidAgent with persistent memory and app card support.
    """
    
    setup_gemini_env()
    
    try:
        if os.path.exists('config.yaml'):
            config = DroidrunConfig.from_yaml('config.yaml')
        else:
            config = DroidrunConfig()
    except Exception:
        config = DroidrunConfig()

    config.agent.reasoning = reasoning
    config.agent.vision = True
    config.agent.max_steps = 50 
    
    variables = {}
    if app_card_instructions:
        variables["app_card_instructions"] = app_card_instructions

    # [ENHANCED] Robust Intercepting Tool Calls
    def speak_wrapper(action_name, args):
        # We lowercase to ensure "Open_App" and "open_app" both trigger the voice
        name = action_name.lower()
        print(f"DEBUG: speak_wrapper triggered for: {name}")

        if "open_app" in name:
            app_name = args.get('app_name') or args.get('package') or "application"
            announce_action(f"Opening {app_name}")
        elif "type" in name:
            announce_action("Typing text")
        elif "click" in name:
            announce_action("Clicking")
        elif "scroll" in name:
            announce_action("Scrolling")
        elif "complete" in name:
            announce_action("Task completed successfully")

    try:
        agent = DroidAgent(
            goal=goal_text,
            config=config,
            custom_tools=CUSTOM_TOOLS,
            variables=variables,
            output_model=None
        )

        # Hook the announcement to tool execution
        agent.on_tool_call = speak_wrapper
        
        # Immediate Startup Confirmation
        announce_action("Systems online. Agent is ready.")
        
        return agent
        
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to initialize agent: {str(e)}")

        

# import traceback
# import json
# import os
# from droidrun import DroidAgent, DroidrunConfig
# from utils import setup_gemini_env
# import pyttsx3
# import threading

# # --- MEMORY FILE PATH ---
# MEMORY_FILE = "session_memory.json"


# def announce_action(text: str):
#     def _speak():
#         try:
#             engine = pyttsx3.init()
#             # Optional: Customize voice/rate
#             engine.setProperty('rate', 180) 
#             engine.say(text)
#             engine.runAndWait()
#         except Exception as e:
#             print(f"TTS Error: {e}")
    
#     # Run in background so the agent doesn't pause while talking
#     threading.Thread(target=_speak, daemon=True).start()

# # --- Custom Tools with Rich Descriptions ---
# def save_note(key: str, value: str, **kwargs) -> str:
#     try:
#         data = {}
#         if os.path.exists(MEMORY_FILE):
#             try:
#                 with open(MEMORY_FILE, 'r') as f: 
#                     data = json.load(f)
#             except: 
#                 pass 
#         data[key] = value
#         with open(MEMORY_FILE, 'w') as f: 
#             json.dump(data, f, indent=2)
#         return f"✓ Saved to memory: {key} = {value}"
#     except Exception as e: 
#         return f"✗ Error saving: {e}"

# def read_notes(**kwargs) -> str:
#     try:
#         if not os.path.exists(MEMORY_FILE): 
#             return "Memory is empty. No data saved yet."
#         with open(MEMORY_FILE, 'r') as f: 
#             data = json.load(f)
#         if not data:
#             return "Memory is empty."
#         return f"Memory Contents:\n{json.dumps(data, indent=2)}"
#     except Exception as e: 
#         return f"✗ Error reading: {e}"

# CUSTOM_TOOLS = {
#     "save_note": {
#         "arguments": ["key", "value"], 
#         "description": """Save information to persistent memory for later retrieval.

# WHEN TO USE:
# - Comparing multiple products/prices (save each one as you find it)
# - Tracking search results across different screens
# - Storing data that will be needed for final decision/comparison
# - Recording details before moving to next step

# USAGE EXAMPLES:
# - save_note(key="jeans_product1", value="Roadster Baggy Jeans ₹1299 40% off")
# - save_note(key="jeans_product2", value="Levi's Baggy ₹2499 20% off")
# - save_note(key="best_price_found", value="₹899")

# IMPORTANT: Use descriptive keys like "product1_price", "item_name", "best_deal" """,
#         "function": save_note
#     },
#     "read_notes": {
#         "arguments": [], 
#         "description": """Retrieve ALL saved information from memory to view or compare.

# WHEN TO USE:
# - Before making final comparison between saved items
# - When you need to recall previously saved prices/details
# - At end of search to review all collected data
# - To check what information was already saved

# RETURNS: JSON object containing all key-value pairs from memory

# EXAMPLE: After saving 3 products, call read_notes() to see all prices together for comparison""",
#         "function": read_notes
#     }
# }

# # --- Factory Function ---
# def create_agent(
#     goal_text: str, 
#     app_card_instructions: str = None, 
#     use_structured_output: bool = False,
#     reasoning: bool = False ,
#     vision: bool = True
    
# ) -> DroidAgent:
#     """
#     Create DroidAgent with persistent memory and app card support.
    
#     Memory tools allow the agent to:
#     - Save data during execution (prices, product details, etc.)
#     - Retrieve saved data for comparison and decision-making
#     - Handle multi-step tasks requiring data accumulation
#     """
    
#     setup_gemini_env()
    
#     try:
#         if os.path.exists('config.yaml'):
#             config = DroidrunConfig.from_yaml('config.yaml')
#         else:
#             config = DroidrunConfig()
#     except Exception:
#         config = DroidrunConfig()

#     config.agent.reasoning = reasoning
#     config.agent.vision = True
#     config.agent.max_steps = 50 
    
#     # Variables that get injected into LLM context
#     variables = {}
#     if app_card_instructions:
#         variables["app_card_instructions"] = app_card_instructions

#     # [NEW] Intercepting Tool Calls
#     # We detect if the agent is about to open an app or click something and announce it.
#     def speak_wrapper(action_name, args):
#         if action_name == "open_app":
#             announce_action(f"Opening {args.get('app_name', 'app')}")
#         elif action_name == "type":
#             announce_action(f"Typing {args.get('text', 'content')}")
#         elif action_name == "click":
#             announce_action("Clicking element")
    
#     try:
#         agent = DroidAgent(
#             goal=goal_text,
#             config=config,
#             custom_tools=CUSTOM_TOOLS,  # ← LLM sees these as available functions
#             variables=variables,
#             output_model=None
#         )

#         agent.on_tool_call = speak_wrapper
#         return agent
        
#     except Exception as e:
#         traceback.print_exc()
#         raise RuntimeError(f"Failed to initialize agent: {str(e)}")
