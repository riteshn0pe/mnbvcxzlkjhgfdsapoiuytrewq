import traceback
import json
import os
from droidrun import DroidAgent, DroidrunConfig
from utils import setup_gemini_env

# --- MEMORY FILE PATH ---
MEMORY_FILE = "session_memory.json"

# --- Custom Tools with Rich Descriptions ---
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
    reasoning: bool = False ,
    vision: bool = True
    
) -> DroidAgent:
    """
    Create DroidAgent with persistent memory and app card support.
    
    Memory tools allow the agent to:
    - Save data during execution (prices, product details, etc.)
    - Retrieve saved data for comparison and decision-making
    - Handle multi-step tasks requiring data accumulation
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
    
    # Variables that get injected into LLM context
    variables = {}
    if app_card_instructions:
        variables["app_card_instructions"] = app_card_instructions
    
    try:
        agent = DroidAgent(
            goal=goal_text,
            config=config,
            custom_tools=CUSTOM_TOOLS,  # ← LLM sees these as available functions
            variables=variables,
            output_model=None
        )
        return agent
        
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to initialize agent: {str(e)}")
