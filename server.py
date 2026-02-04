import os
import json
import logging
import asyncio
import subprocess
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent_brain import create_agent , announce_action

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DroidRunServer")

# --- Configuration ---
MACRO_DIR = "macros"
APP_CARD_DIR = "app_cards" 
MEMORY_FILE = "session_memory.json"
HISTORY_FILE = "recent_query.json" # [NEW] Stores last 10 commands

os.makedirs(MACRO_DIR, exist_ok=True)
os.makedirs(APP_CARD_DIR, exist_ok=True)

# --- Data Models (Unchanged) ---
class CommandRequest(BaseModel):
    command: str
    app_card: Optional[str] = None
    use_structured_output: bool = False
    reasoning: bool = False 

# Wireless Request Model
class WirelessRequest(BaseModel):
    ip: str
    port: str

class Macro(BaseModel):
    name: str
    template: str

class AppGuide(BaseModel):
    app_name: str
    title: str
    content: str

class StatusResponse(BaseModel):
    status: str
    logs: List[str]
    result: Optional[str] = None

# --- Global State ---
class AgentState:
    def __init__(self):
        self.status = "idle"
        self.logs = []
        self.result = None
        self._active_task: Optional[asyncio.Task] = None
        self.original_keyboard: Optional[str] = None
        self.step_count = 0 

state = AgentState()

#  Wireless ADB Helper
def connect_wireless_adb(ip: str, port: str):
    """Attempts to connect to a device via Wireless ADB."""
    target = f"{ip}:{port}"
    logger.info(f"📡 Connecting to wireless device: {target}")
    
    try:
        # Run adb connect
        proc = subprocess.run(
            ["adb", "connect", target], 
            capture_output=True, text=True, timeout=10
        )
        output = proc.stdout.strip()
        
        if "connected to" in output:
            return {"success": True, "message": f"Connected to {target}"}
        else:
            return {"success": False, "message": f"Failed: {output}"}
            
    except Exception as e:
        logger.error(f"Wireless connection failed: {e}")
        return {"success": False, "message": str(e)}

# --- Helpers ---
def get_current_keyboard() -> Optional[str]:
    try:
        result = subprocess.run(
            ["adb", "shell", "settings", "get", "secure", "default_input_method"], 
            capture_output=True, text=True, timeout=5
        )
        kb = result.stdout.strip()
        return kb if kb and "null" not in kb else None
    except Exception as e:
        logger.warning(f"Keyboard detection failed: {e}")
        return None

def set_keyboard(ime_id: str):
    if ime_id:
        try:
            subprocess.run(["adb", "shell", "ime", "set", ime_id], check=True, timeout=5)
        except Exception as e:
            logger.error(f"Keyboard reset failed: {e}")

def clear_memory():
    """Wipes the short-term memory for a new session."""
    if os.path.exists(MEMORY_FILE):
        try:
            os.remove(MEMORY_FILE)
            logger.info("🧠 Session memory cleared.")
        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")

# [NEW] History Helper
def update_history(command: str):
    """Saves the latest command to history, keeping only unique last 10."""
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f: history = json.load(f)
            except: pass
        
        # Remove if exists (to move to top)
        if command in history:
            history.remove(command)
        
        # Add to top
        history.insert(0, command)
        
        # Keep only 10
        if len(history) > 10:
            history = history[:10]
            
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update history: {e}")

# --- Enhanced Background Worker ---
async def run_droid_task_logic(task_text: str, app_card: str, use_structured: bool , reasoning : bool):
    state.status = "running"
    state.logs.clear()
    state.result = None
    state.step_count = 0
    state.original_keyboard = get_current_keyboard()
    
    # [NEW] Reset Memory & Update History
    clear_memory()
    update_history(task_text)
    
    logger.info(f"🚀 Starting task: {task_text}")
    if state.original_keyboard:
        logger.info(f"📱 Original keyboard: {state.original_keyboard}")

    try:
        # Create agent with app guide
        agent = create_agent(task_text, app_card, use_structured, reasoning=reasoning)
        
        # Execute with step monitoring
        state.logs.append(f"▶️ Executing: {task_text}")
        
        # Set timeout to prevent infinite hanging
        result = await asyncio.wait_for(agent.run(), timeout=300)  # 5 min max

        # [CRITICAL FIX] Robustly extract output from varied DroidRun result objects
        # The result object structure changes depending on success/failure modes.
        final_output = "Task Completed"
        
        # 1. Determine the content
        if use_structured and hasattr(result, 'structured_output'):
            final_output = str(result.structured_output)
        elif hasattr(result, 'output'):
            final_output = str(result.output)
        elif hasattr(result, 'result'):
             final_output = str(result.result)
        elif hasattr(result, 'reason'): # Common in 'complete(reason=...)'
             final_output = str(result.reason)
        else:
             final_output = str(result) # Fallback to string representation

        # 2. Determine success status
        is_success = True
        if hasattr(result, 'success'):
            is_success = result.success

        # 3. Process Result
        if is_success:
            state.status = "success"
            
            # Check for completion signal
            if "TASK_COMPLETE" in final_output:
                state.result = final_output.replace("TASK_COMPLETE:", "").strip()
                state.logs.append(f"✅ Task completed: {state.result}")
            else:
                state.result = final_output
                state.logs.append(f"✅ Success: {state.result}")
                
        else:
            state.status = "failed"
            state.result = final_output or "Unknown failure"
            state.logs.append(f"❌ Failed: {state.result}")
            
            # Check for common errors
            if "Manager response invalid" in state.result:
                state.logs.append("💡 Hint: The AI response format was unexpected. Try rephrasing your command.")
            elif "timeout" in state.result.lower():
                state.logs.append("💡 Hint: Task took too long. Try breaking it into smaller steps.")
            elif "rate limit" in state.result.lower() or "429" in state.result:
                state.logs.append("💡 Hint: Hit API rate limit. Wait a moment and try again.")
            
    except asyncio.TimeoutError:
        state.status = "failed"
        state.result = "Task exceeded 5 minute timeout"
        state.logs.append("⏱️ Task timed out after 5 minutes")
        
    except asyncio.CancelledError:
        state.status = "stopped"
        state.logs.append("🛑 Task manually stopped by user")
        
    except Exception as e:
        state.status = "error"
        state.result = str(e)
        state.logs.append(f"💥 Error: {str(e)}")
        logger.exception("Agent crashed with exception:")
        
        # Provide helpful error context
        if "Manager response invalid" in str(e):
            state.logs.append("💡 This is a formatting issue. The AI output didn't match expected structure.")
        elif "429" in str(e) or "rate_limit" in str(e).lower():
            state.logs.append("💡 Hit API rate limit. Please wait 60 seconds before retrying.")
        
    finally:
        # Always restore keyboard
        if state.original_keyboard:
            logger.info("♻️ Restoring original keyboard...")
            set_keyboard(state.original_keyboard)
        state._active_task = None
        logger.info(f"🏁 Task ended with status: {state.status}")

# --- API Endpoints ---
app = FastAPI()

@app.get("/health")
async def health(): 
    return {"status": "ok", "agent_status": state.status}

@app.get("/status")
async def get_status():
    return {
        "status": state.status,
        "logs": state.logs[-100:],  
        "result": state.result,
        "step_count": state.step_count
    }

@app.post("/execute")
async def execute(req: CommandRequest):
    if state.status == "running" and state._active_task:
        raise HTTPException(409, "Agent is busy. Stop current task first.")
    
    if not req.command or len(req.command.strip()) < 3:
        raise HTTPException(400, "Command too short or empty")
    
    state._active_task = asyncio.create_task(
        run_droid_task_logic(req.command, req.app_card, req.use_structured_output , req.reasoning)
    )
    return {"message": "Task started", "command": req.command}

@app.post("/stop")
async def stop():
    if state._active_task:
        state._active_task.cancel()
        if state.original_keyboard: 
            set_keyboard(state.original_keyboard)
        return {"message": "Task stopped"}
    return {"message": "No active task"}

@app.post("/fix_keyboard")
async def fix_keyboard_endpoint():
    default = "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"
    target = state.original_keyboard if state.original_keyboard else default
    set_keyboard(target)
    return {"message": f"Keyboard reset to: {target}"}

# --- [NEW] History Endpoint ---
@app.get("/history")
async def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f: return json.load(f)
        except: pass
    return []

# --- MACRO MANAGEMENT ---
@app.get("/macros")
async def list_macros():
    res = []
    if os.path.exists(MACRO_DIR):
        for f in os.listdir(MACRO_DIR):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(MACRO_DIR, f)) as file:
                        res.append(json.load(file))
                except: pass
    return res

@app.post("/macros")
async def create_macro(m: Macro):
    safe = "".join(c for c in m.name if c.isalnum() or c==' ').strip().replace(' ', '_').lower()
    try:
        with open(os.path.join(MACRO_DIR, f"{safe}.json"), "w") as f:
            json.dump(m.model_dump(), f, indent=2)
        return {"status": "saved", "filename": f"{safe}.json"}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- APP GUIDE MANAGEMENT ---
@app.get("/app_guides")
async def list_guides():
    res = []
    if os.path.exists(APP_CARD_DIR):
        for f in os.listdir(APP_CARD_DIR):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(APP_CARD_DIR, f)) as file:
                        res.append(json.load(file))
                except: pass
    return res

@app.post("/app_guides")
async def create_guide(g: AppGuide):
    safe_title = "".join(c for c in g.title if c.isalnum() or c==' ').strip().replace(' ', '_').lower()
    try:
        with open(os.path.join(APP_CARD_DIR, f"{safe_title}.json"), "w") as f:
            json.dump(g.model_dump(), f, indent=2)
        return {"status": "saved", "filename": f"{safe_title}.json"}
    except Exception as e:
        raise HTTPException(500, str(e))
    
# Wireless Connection Endpoint
@app.post("/connect_wireless")
async def connect_wireless_endpoint(req: WirelessRequest):
    logger.info(f"📶 Wireless request received: {req.ip}:{req.port}")
    
    # 1. Announce intent
    announce_action(f"Initiating wireless connection to {req.ip}")
    
    # 2. Attempt connection
    result = connect_wireless_adb(req.ip, req.port)
    
    if result["success"]:
        # 3. Success Voice
        announce_action("Wireless connection established successfully")
        return {"status": "success", "detail": result["message"]}
    else:
        # 4. Failure Voice
        announce_action("Connection failed. Please check IP and Port")
        raise HTTPException(status_code=400, detail=result["message"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
