import tkinter.font as tkfont
from tkinter import ttk

def adjust_column_widths(tree, max_width=500):
    """
    Adjusts the column widths of a ttk.Treeview to fit the content and headers.
    
    Args:
        tree: The ttk.Treeview widget.
        max_width: Maximum width for any column to prevent excessive expansion.
    """
    # Get the font used for the Treeview content and Heading
    # Note: style font can be different, we try to use a safe default if not easily detectable
    # Arial 12 is the default set in HistoricoFrame style
    font_content = tkfont.Font(family="Arial", size=12)
    font_header = tkfont.Font(family="Arial", size=14, weight="bold")
    
    # Iterate through each column
    for col in tree["columns"]:
        # Measure header width
        header_text = tree.heading(col)["text"]
        w_header = font_header.measure(header_text) + 20 # Add padding
        
        # Measure content width
        w_content = 0
        for item in tree.get_children():
            # Get value for this column
            val = str(tree.set(item, col))
            w_val = font_content.measure(val)
            if w_val > w_content:
                w_content = w_val
        
        # Take the maximum of header and content, with padding
        best_width = max(w_header, w_content + 20)
        
        # Apply max cap
        if best_width > max_width:
            best_width = max_width
            
        tree.column(col, width=best_width)
