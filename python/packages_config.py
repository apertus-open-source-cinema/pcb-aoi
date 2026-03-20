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

# Try to import from the existing pcb_processing module
try:
    from pcb_processing import parse_mnt_file
except ImportError:
    parse_mnt_file = None

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
        package_data[values[0]] = {
            "width_mm": float(width_str),
            "length_mm": float(length_str)
        }
    import json
    with open("packages_config.json", "w") as f:
        json.dump(package_data, f, indent=2)
    status.config(text="Data saved successfully")

def on_closing(tree, status):
    """Handle window closing event."""
    save_data(tree, status)
    tree.master.destroy()

def create_packages_config_gui(master=None):
    """Create the main GUI window.
    
    Args:
        master: Optional parent Tk window. If None, creates a new Toplevel window.
    
    Returns:
        Dictionary with 'root' reference for cleanup if needed.
    """
    owns_root = False
    if master is None:
        root = tk.Tk()
        owns_root = True
    else:
        root = tk.Toplevel(master)
    
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
    editing = None

    def on_double_click(event):
        global editing
        item = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        if item and column in ("#3", "#4"):  # Width and Length columns
            editing = (item, column)
            text = tree.item(item, "values")[int(column[1:]) - 1]
            x, y, width, height = tree.bbox(item, column)
            entry = tk.Entry(root, width=width, relief=tk.FLAT, borderwidth=0)
            entry.insert(0, text)
            entry.place(x=x+1, y=y+1, width=width-2, height=height-2)
            entry.focus_set()
            entry.select_range(0, tk.END)
            entry.bind("<Return>", lambda e: update_value(entry, item, column))
            entry.bind("<Escape>", lambda e: cancel_edit(entry, item, column))

    def on_return_press(event):
        if editing:
            item, column = editing
            entry = root.focus_get()
            if isinstance(entry, tk.Entry):
                update_value(entry, item, column)

    def update_value(entry, item, column):
        global editing
        new_value = entry.get()
        try:
            float(new_value)  # Validate that it's a number
            tree.item(item, values=update_tuple(tree.item(item, "values"), int(column[1:]) - 1, new_value))
            entry.destroy()
            editing = None
        except ValueError:
            entry.config(background="pink")
            entry.after(500, lambda: entry.config(background="white"))

    def cancel_edit(entry, item, column):
        global editing
        entry.destroy()
        editing = None

    def update_tuple(tup, index, value):
        return tup[:index] + (value,) + tup[index+1:]

    tree.bind("<Double-1>", on_double_click)
    tree.bind("<Return>", on_return_press)

    # Add scrollbars
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
    hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
    tree.configure(yscroll=vsb.set, xscroll=hsb.set)

    # Populate table
    def populate_table():
        if parse_mnt_file:
            # Try to find .mnt file in current directory
            mnt_files = [f for f in os.listdir() if f.endswith('.mnt')]
            if mnt_files:
                components = parse_mnt_file(mnt_files[0])
                packages = get_unique_packages(components)

                for package, count in sorted(packages.items()):
                    width, length = get_package_dimensions(package)
                    tree.insert("", "end", values=(package, count, f"{width:.1f}", f"{length:.1f}"))
            else:
                tree.insert("", "end", values=("No .mnt file found", "", "", ""))
        else:
            tree.insert("", "end", values=("pcb_processing.py not found", "", "", ""))

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
    root.bind("<Double-1>", on_double_click)
    root.bind("<Return>", on_return_press)

    # Handle window closing properly
    def handle_closing():
        save_data(tree, status)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", handle_closing)
    
    # Run mainloop only if we created our own root
    if owns_root:
        root.mainloop()
    
    return {'root': root}

if __name__ == "__main__":
    create_packages_config_gui()