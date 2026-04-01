#!/usr/bin/python
"""
Packages Configuration GUI

This script creates a tkinter GUI window that displays a table of unique packages
with their dimensions (width and length in mm).
"""

import tkinter as tk
from tkinter import ttk
import os
import sys
import json
from window_manager import apply_saved_geometry, set_window_geometry

# Note: parse_mnt_file import removed from module level to avoid circular 
# dependency with pcb_processing.py. If needed, import it locally within functions.

def _get_parser():
    """Helper to get mnt parser without circular imports."""
    from pcb_processing import parse_mnt_file
    return parse_mnt_file

# Load package dimensions from JSON file
try:
    with open("packages_config.json", "r") as f:
        package_data = json.load(f)
    PACKAGE_DIMENSIONS = {pkg: (data["width_mm"], data["length_mm"]) for pkg, data in package_data.items()}
except (FileNotFoundError, json.JSONDecodeError):
    PACKAGE_DIMENSIONS = {}

def get_unique_packages(components):
    """Extract unique packages from components list."""
    packages = {}
    for comp in components:
        package = comp.get("package", "")
        if package:
            packages[package] = packages.get(package, 0) + 1
    return packages

def get_package_dimensions(package):
    """Get dimensions for a package."""
    return PACKAGE_DIMENSIONS.get(package, (0.0, 0.0))

def save_data(tree, status):
    """Save package data to JSON file."""
    package_data = {}
    for item in tree.get_children():
        values = tree.item(item, "values")
        # Handle empty strings by converting to 0.0
        width_str = values[2] if values[2] else '0.0'
        length_str = values[3] if values[3] else '0.0'
        w, l = float(width_str), float(length_str)
        if w > 0 and l > 0:
            package_data[values[0]] = {
                "width_mm": w,
                "length_mm": l
            }
    import json
    with open("packages_config.json", "w") as f:
        json.dump(package_data, f, indent=2)
    status.config(text="Data saved successfully")

def on_closing(tree, status):
    """Handle window closing event."""
    save_data(tree, status)
    tree.master.destroy()

def create_packages_config_gui(master=None, components=None, on_change=None):
    """Create the main GUI window.
    
    Args:
        master: Optional parent Tk window. If None, creates a new Toplevel window.
        on_change: Optional callback function called when dimensions are modified.
    
    Returns:
        Dictionary with 'root' reference for cleanup if needed.
    """
    owns_root = False
    if master is None:
        root = tk.Tk()
        owns_root = True
    else:
        root = tk.Toplevel(master)
    
    # Apply saved geometry
    has_saved_geometry = apply_saved_geometry(root, "PackagesConfig")

    root.title("Packages Configuration")

    # Main frame
    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    main_frame.rowconfigure(0, weight=0)  # Title row - no weight
    main_frame.rowconfigure(1, weight=1)  # Table row - expandable
    main_frame.rowconfigure(2, weight=0)  # Status frame row - no weight
    main_frame.rowconfigure(3, weight=0)  # Button row - no weight
    main_frame.columnconfigure(0, weight=1)  # Main column - expandable

    # Title
    title = ttk.Label(main_frame, text="Packages Configuration", font=("Arial", 16, "bold"))
    title.grid(row=0, column=0, columnspan=3, pady=(0, 10))

    # Table frame
    table_frame = ttk.Frame(main_frame)
    table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)

    # Create Treeview with scrollbars
    columns = ("Package", "Count", "Width (mm)", "Length (mm)")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings")
    tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Configure columns
    tree.heading("Package", text="Package")
    tree.heading("Count", text="Count")
    tree.heading("Width (mm)", text="Width (mm)", anchor="center")
    tree.heading("Length (mm)", text="Length (mm)", anchor="center")

    # Configure column widths
    tree.column("Package", anchor="w")
    tree.column("Count", width=80, anchor="center")
    tree.column("Width (mm)", anchor="center")
    tree.column("Length (mm)", anchor="center")

    # Make width and length columns editable
    def on_double_click(event):
        # Clean up any existing entry widgets
        for widget in tree.winfo_children():
            if isinstance(widget, tk.Entry):
                widget.destroy()

        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = tree.identify_column(event.x)
        # Only allow editing Width (#3) and Length (#4)
        if column not in ("#3", "#4"):
            return

        item = tree.identify_row(event.y)
        if not item:
            return

        # Get cell coordinates
        bbox = tree.bbox(item, column)
        if not bbox:
            return
        x, y, w, h = bbox

        # Get current value
        col_idx = int(column[1:]) - 1
        values = tree.item(item, "values")
        current_val = values[col_idx]

        # Create entry widget inside the treeview
        entry = tk.Entry(tree, relief=tk.FLAT)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_val)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def save_edit(event=None):
            try:
                val = float(entry.get())
                if val <= 0:
                    raise ValueError("Dimensions must be positive")

                new_values = list(tree.item(item, "values"))
                new_values[col_idx] = str(val)
                tree.item(item, values=new_values)

                # Update global dictionary immediately if both dimensions are valid
                pkg_name = new_values[0]
                w, l = float(new_values[2]), float(new_values[3])
                if w > 0 and l > 0:
                    PACKAGE_DIMENSIONS[pkg_name] = (w, l)
                    # Notify listener that data has changed
                    if on_change:
                        on_change()

                entry.destroy()
            except ValueError:
                entry.configure(bg="#ffcccc")

        def cancel_edit(event=None):
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<Escape>", cancel_edit)
        entry.bind("<FocusOut>", lambda e: cancel_edit())

    tree.bind("<Double-1>", on_double_click)

    # Add scrollbars
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
    hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
    tree.configure(yscroll=vsb.set, xscroll=hsb.set)

    # Populate table
    def populate_table():
        # Use PACKAGE_DIMENSIONS which is already loaded from JSON
        # and overlay component counts if provided
        counts = {}
        if components:
            counts = get_unique_packages(components)
        
        # Combine all known packages
        all_packages = set(PACKAGE_DIMENSIONS.keys()) | set(counts.keys())
        
        for package in sorted(all_packages):
            count = counts.get(package, 0)
            width, length = get_package_dimensions(package)
            count_str = str(count) if count > 0 else "-"
            tree.insert("", "end", values=(package, count_str, f"{width}", f"{length}"))

    populate_table()

    # Status bar
    status_frame = ttk.Frame(main_frame)
    status_frame.grid(row=2, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
    status_frame.columnconfigure(0, weight=1)

    # Save button
    save_button = ttk.Button(main_frame, text="Save", command=lambda: save_data(tree, status))
    save_button.grid(row=3, column=0, pady=(5, 0), sticky=(tk.W, tk.E))

    status = ttk.Label(status_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
    status.pack(fill=tk.X, expand=True)

    # Center window
    def center_window():
        root.update_idletasks()
        width = root.winfo_width()
        length = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (length // 2)
        root.geometry(f'{width}x{length}+{x}+{y}')

    if not has_saved_geometry:
        center_window()

    # Run the GUI
    def on_resize(event):
        # Update column widths when window is resized
        if tree.winfo_width() > 200:
            # Get the total width available for the three columns
            total_width = tree.winfo_width()
            # Fixed width for Count column
            count_width = 80
            # Calculate remaining width for the three editable columns
            remaining_width = total_width - count_width
            if remaining_width > 0:
                # Distribute remaining width equally among the three columns
                column_width = remaining_width // 3
                tree.column("Package", width=column_width)
                tree.column("Width (mm)", width=column_width)
                tree.column("Length (mm)", width=column_width)
        
        # Update scrollbar positions
        vsb.set(*tree.yview())
        hsb.set(*tree.xview())

    root.bind("<Configure>", on_resize)

    # Handle window closing properly
    def handle_closing():
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", handle_closing)

    # Ensure geometry is saved even if the parent destroys this window
    root.bind("<Destroy>", lambda e: set_window_geometry(root, "PackagesConfig") if e.widget == root else None)
    
    # Run mainloop only if we created our own root
    if owns_root:
        root.mainloop()
    
    return {'root': root}

if __name__ == "__main__":
    create_packages_config_gui()