import traceback
print("Starting imports")
try:
    import customtkinter as ctk
    from gui.app import App
except Exception as e:
    print("Import error:", e)
    import sys; sys.exit(1)

import sys
# sys.settrace(trace_calls) # disabling trace since we know init works

try:
    print("Instantiating App")
    app = App()
    print("App instantiated successfully. Starting mainloop...")
    # Add a timeout to kill it if it hangs but we want to see if it reaches mainloop
    app.after(1000, lambda: print("Mainloop is running!"))
    app.mainloop()
except Exception as e:
    print("Error during App loop:", e)
    traceback.print_exc()
