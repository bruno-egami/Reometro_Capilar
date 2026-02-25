import traceback
print("Starting imports")
try:
    import customtkinter as ctk
    from gui.app import App
    print("Imports done")
except Exception as e:
    print("Import error:", e)
    import sys; sys.exit(1)

import sys
def trace_calls(frame, event, arg):
    if event == 'call':
        func_name = frame.f_code.co_name
        file_name = frame.f_code.co_filename
        if 'gui' in file_name or 'Reometer' in file_name:
            print(f"Calling {func_name} at {file_name}:{frame.f_lineno}")
    return trace_calls

sys.settrace(trace_calls)

print("Instantiating App")
try:
    app = App()
    print("App instantiated successfully.")
except Exception as e:
    print("Error during App instantiation:", e)
    traceback.print_exc()
