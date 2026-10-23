import os
import frappe


_debug_initialized = False


def active_debug():
    global _debug_initialized
    if _debug_initialized:
        return
    # An unauthenticated remote debugger runs any code it is sent: only on a
    # developer-mode site (the Docker dev setup), never on a production bench,
    # whatever the environment says. debugpy is not a runtime dependency either:
    # docker/init.sh installs it for development.
    if os.environ.get("DEBUG_MODE") == "1" and frappe.conf.developer_mode:
        try:
            import debugpy
            if not debugpy.is_client_connected():
                debugpy.listen(("0.0.0.0", 5678))
                print("[DEBUG] ==================================",flush=True)
                print("[DEBUG] ==== Start debug at port 5678 ====",flush=True)
            _debug_initialized = True
        except Exception as e:
            print(f"[DEBUG] Could not start debugpy: {e}", flush=True)