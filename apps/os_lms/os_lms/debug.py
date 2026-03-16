import os
import frappe


_debug_initialized = False


def active_debug():
    global _debug_initialized
    if _debug_initialized:
        return
    if os.environ.get("DEBUG_MODE") == "1":
        try:
            import debugpy
            if not debugpy.is_client_connected():
                debugpy.listen(("0.0.0.0", 5678))
                print("[DEBUG] ==================================",flush=True)
                print("[DEBUG] ==== Start debug at port 5678 ====",flush=True)
            _debug_initialized = True
        except Exception as e:
            print(f"[DEBUG] Could not start debugpy: {e}", flush=True)