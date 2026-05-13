def pre_find_module_path(hook_api):
    # The local Python installation exposes tkinter correctly, but PyInstaller's
    # Tcl/Tk auto-detection incorrectly flags it as "broken" and excludes it.
    # Let the standard module resolution proceed normally.
    return
