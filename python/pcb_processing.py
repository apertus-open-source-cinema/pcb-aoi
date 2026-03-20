#!/usr/bin/python
"""
PCB AOI (Automated Optical Inspection) Processing Script

This script processes PCB images, detects fiducials, applies perspective
transformations, and overlays component positions.
"""

import sys
import os
import numpy as np
import cv2

# Import packages config module first
# Add current directory to path to handle both direct and module execution
_python_dir = os.path.dirname(os.path.abspath(__file__))
if _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)
try:
    from packages_config import create_packages_config_gui, PACKAGE_DIMENSIONS
except ImportError:
    create_packages_config_gui = None
    PACKAGE_DIMENSIONS = {}
    print("Warning: Could not import packages_config module")

try:
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk
except ImportError:
    tk = None
    ttk = None
    Image = None
    ImageTk = None


# Global Variables
fiducialTemplate = './python/templates/fiducial.tif'
fiducialPositions = []  # Detected fiducial positions in image
fiducialBoardPositions = {}  # Fiducial positions from .mnt file (mm, board coords)
pixel_per_mm_scale = 0
pcb_w = 1
pcb_h = 1

# Image Processing Functions

def find_fiducial_in_region(img_gray, template, region):
    """Find a fiducial within a specific region of the image."""
    x, y, w, h = region
    #print(f'ROI: {w}x{h}')

    roi = img_gray[y:y+h, x:x+w]
    result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    
    template_w, template_h = template.shape[::-1]
    _, _, _, max_loc = cv2.minMaxLoc(result)
    
    # Calculate center position
    center_x = x + max_loc[0] + template_w // 2
    center_y = y + max_loc[1] + template_h // 2
    
    return (center_x, center_y)


def find_all_fiducials(img_gray, template):
    """Find all 4 fiducials by searching in image quadrants.
    
    Returns:
        List of 4 positions ordered as: top-left, bottom-left, bottom-right, top-right
    """
    height, width = img_gray.shape[:2]
    half_w = width // 2 
    half_h = height // 2
    
    # Search in 4 quadrants
    positions = [ # order: top-left, bottom-left, bottom-right, top-right
        find_fiducial_in_region(img_gray, template, (0, 0, half_w, half_h)),
        find_fiducial_in_region(img_gray, template, (0, half_h, half_w, half_h)),
        find_fiducial_in_region(img_gray, template, (half_w, half_h, half_w, half_h)),
        find_fiducial_in_region(img_gray, template, (half_w, 0, half_w, half_h))
    ]
    
    # Sort to get: top-left, top-right, bottom-right, bottom-left
    #sorted_by_y = sorted(positions, key=lambda p: p[1])
    #top_points = sorted_by_y[:2]
    #bottom_points = sorted_by_y[2:]
    
    return positions
    #[
    #    min(top_points, key=lambda p: p[0]),
    #    max(top_points, key=lambda p: p[0]),
    #    max(bottom_points, key=lambda p: p[0]),
    #    min(bottom_points, key=lambda p: p[0]),
    #]
def distance_2d(point1, point2):
    """
    Calculates the Euclidean distance between two 2D points.
    
    Args:
        point1 (tuple or list): First point as (x1, y1).
        point2 (tuple or list): Second point as (x2, y2).
    
    Returns:
        float: The distance between the points.
    """
    dx = point1[0] - point2[0]
    dy = point1[1] - point2[1]
    return (dx**2 + dy**2)**0.5

def apply_perspective_transform(image, src_points, pcb_width=None, pcb_height=None, fiducial_positions_mm=None):
    """Apply 4-point perspective transform to get top-down view.
    
    Args:
        image: Input image
        src_points: Source points in image pixel coordinates
        pcb_width: PCB width in mm (optional)
        pcb_height: PCB height in mm (optional)
        fiducial_positions_mm: Dict mapping fiducial names to (x,y) positions in mm (optional)
    
    Returns:
        warped: Transformed image
        transform_matrix: Perspective transform matrix
        output_width: Output width in pixels
        output_height: Output height in pixels
    """
    def order_points(pts):
        """Order points: top-left, top-right, bottom-right, bottom-left"""
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).reshape(-1)
        rect = np.zeros((4, 2), dtype="float32")
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        rect[1] = pts[np.argmin(d)]
        rect[3] = pts[np.argmax(d)]
        return rect

    # This moves rect points outwards to match pcb corners
    # This is needed because the fiducials are usually inset from the actual PCB edges, 
    # and we want the final transform to cover the entire PCB area.
    # We can estimate the offset by comparing the detected fiducial positions to their 
    # expected positions based on the PCB dimensions and fiducial board positions (if available).
    #calculation in mm
    offset_FID1 = ( pcb_width/2 - abs(fiducial_positions_mm['FID1'][0]), pcb_height/2 - abs(fiducial_positions_mm['FID1'][1]) ) 
    offset_FID2 = ( pcb_width/2 - abs(fiducial_positions_mm['FID2'][0]), pcb_height/2 - abs(fiducial_positions_mm['FID2'][1]) )  
    offset_FID3 = ( pcb_width/2 - abs(fiducial_positions_mm['FID3'][0]), pcb_height/2 - abs(fiducial_positions_mm['FID3'][1]) )  
    offset_FID4 = ( pcb_width/2 - abs(fiducial_positions_mm['FID4'][0]), pcb_height/2 - abs(fiducial_positions_mm['FID4'][1]) )  

    rect = order_points(np.asarray(src_points, np.float32))
    # Convert to numpy array for mutable operations and OpenCV compatibility
    #rect = np.asarray(src_points, dtype=np.float32)

    # Calculate distances between fiducials in pixels 
    fid_width_px = distance_2d(rect[0], rect[1])
    fid_height_px = distance_2d(rect[0], rect[3])    

    # Calculate distances between fiducials in mm 
    fid_width_mm = distance_2d(fiducial_positions_mm['FID1'], fiducial_positions_mm['FID2'])
    fid_height_mm = distance_2d(fiducial_positions_mm['FID1'], fiducial_positions_mm['FID4'])

    #combine offset and fiducial positions to move rect points outwards and convert from mm to pixels
    if fiducial_positions_mm and pcb_width and pcb_height:
        rect[0][0] -= offset_FID1[0] * (fid_width_px / fid_width_mm)
        rect[0][1] -= offset_FID1[1] * (fid_height_px / fid_height_mm)
        
        rect[1][0] += offset_FID2[0] * (fid_width_px / fid_width_mm)
        rect[1][1] -= offset_FID2[1] * (fid_height_px / fid_height_mm)
        
        rect[2][0] += offset_FID3[0] * (fid_width_px / fid_width_mm)
        rect[2][1] += offset_FID3[1] * (fid_height_px / fid_height_mm)

        rect[3][0] -= offset_FID4[0] * (fid_width_px / fid_width_mm)
        rect[3][1] += offset_FID4[1] * (fid_height_px / fid_height_mm)

    width_px_per_mm = fid_width_px / fid_width_mm
    height_px_per_mm = fid_height_px / fid_height_mm
    # If PCB dimensions and fiducial positions are provided, use them to calculate scale
    #if pcb_width is not None and pcb_height is not None and fiducial_positions_mm:
        # Calculate expected distances between fiducials based on their board positions
       # expected_distances = []
        
        # Get fiducial names in the same order as src_points
        # fiducial_names = []
        # for point in src_points:
        #     # Find the closest fiducial in the image
        #     min_dist = float('inf')
        #     closest_fid = None
        #     for fid_name, fid_pos in fiducial_positions_mm.items():
        #         # Convert board position to image coordinate system (flip y)
        #         board_x, board_y = fid_pos
        #         img_x = board_x + pcb_width/2
        #         img_y = -(board_y - pcb_height/2)  # Flip y and center
                
        #         # Calculate distance to this point
        #         dist = np.sqrt((point[0] - img_x)**2 + (point[1] - img_y)**2)
        #         if dist < min_dist:
        #             min_dist = dist
        #             closest_fid = fid_name
        #     fiducial_names.append(closest_fid)
        
        # Calculate expected distances between fiducials
        # if len(fiducial_names) == 4:
        #     # Map fiducial names to their expected positions
        #     fid_to_pos = {}
        #     for fid_name in fiducial_names:
        #         if fid_name in fiducial_positions_mm:
        #             x, y = fiducial_positions_mm[fid_name]
        #             # Convert to coordinate system with origin at center
        #             fid_to_pos[fid_name] = (x - pcb_width/2, -(y - pcb_height/2))
            
        #     # Calculate distances between adjacent fiducials
        #     if len(fid_to_pos) == 4:
        #         # Order: top-left, top-right, bottom-right, bottom-left
        #         expected_width = abs(fid_to_pos[fiducial_names[0]][0] - fid_to_pos[fiducial_names[1]][0])
        #         expected_height = abs(fid_to_pos[fiducial_names[0]][1] - fid_to_pos[fiducial_names[3]][1])
                
        #         # Use expected dimensions if they make sense
        #         if expected_width > 0 and expected_height > 0:
        #             output_width = int(expected_width)
        #             output_height = int(expected_height)
        #         else:
        #             output_width = int(fid_width_px)
        #             output_height = int(fid_height_px)
        #     else:
        #         output_width = int(fid_width_px)
        #         output_height = int(fid_height_px)
        # else:
    output_width = int(pcb_width * fid_width_px / fid_width_mm)
    output_height = int(pcb_height * fid_height_px / fid_height_mm)

    # Destination corners in pixels taking into account the pcb_width and pcb_height (in mm) if provided 
    dst = np.array([
        [0, 0],
        [output_width -1, 0],
        [output_width -1, output_height -1],
        [0, output_height -1]
    ], dtype="float32")
    
    # Compute transform and apply
    # requires point order in: top-left, bottom-left, bottom-right, top-right
    transform_matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, transform_matrix, (output_width, output_height))
    
    return warped, transform_matrix, output_width, output_height


# Component Position Functions

def parse_mnt_file(path):
    """Parse component placement file.
    
    Returns:
        List of component dicts with keys: designator, x, y, rotation, value, package
    Also populates fiducialBoardPositions global for fiducials.
    """
    global fiducialBoardPositions
    fiducialBoardPositions.clear()
    components = []
    
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            parts = line.split()
            if len(parts) < 6:
                continue
            
            try:
                designator = parts[0]
                x = float(parts[1])
                y = float(parts[2])
                rotation = float(parts[3])
                value = parts[4]
                package = parts[5]
            except ValueError:
                continue
            
            components.append({
                "designator": designator,
                "x": x, "y": y,
                "rotation": rotation,
                "value": value,
                "package": package,
            })
            
            # Extract fiducial positions
            if designator.startswith("FID") and len(designator) <= 4:
                fiducialBoardPositions[designator] = (x, y)
                print(f"Found fiducial {designator} at ({x}, {y})")

    return components


def parse_pcb_config(path):
    """Parse PCB configuration file."""
    cfg = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = [p.strip() for p in line.split("=", 1)]
                if key in ("pcb_width", "pcb_height"):
                    try:
                        cfg[key] = float(value)
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass
    
    return cfg


def compute_board_to_image_transform(pcb_width, pcb_height, img_width, img_height):
    """Compute perspective transform from board coords to image coords."""
    half_w = pcb_width / 2.0
    half_h = pcb_height / 2.0
    
    # Board corners: top-left, top-right, bottom-right, bottom-left
    board_corners = np.array([
        [-half_w,  half_h],
        [ half_w,  half_h],
        [ half_w, -half_h],
        [-half_w, -half_h],
    ], dtype=np.float32)
    
    # Flip y for image space (board y-up, image y-down)
    board_corners[:, 1] *= -1.0
    
    # Image corners
    img_corners = np.array([
        [0.0, 0.0],
        [img_width - 1, 0.0],
        [img_width - 1, img_height - 1],
        [0.0, img_height - 1],
    ], dtype=np.float32)
    
    return cv2.getPerspectiveTransform(board_corners, img_corners)


def transform_component_positions(components, transform_matrix, img_width, img_height):
    """Transform component positions from board coords to image pixels."""
    overlay_points = []
    half_w = img_width / 2.0
    half_h = img_height / 2.0
    
    for comp in components:
        designator = comp.get("designator", "")
        package = comp.get("package", "")
        rotation = comp.get("rotation", 0.0)
        
        x, y = comp.get("x"), comp.get("y")
        if x is None or y is None:
            continue
        
        # Convert board coords to image coords (flip y)
        pt = np.array([[[x, -y]]], dtype=np.float32)
        
        if transform_matrix is not None:
            mapped = cv2.perspectiveTransform(pt, transform_matrix)
            px = float(mapped[0, 0, 0])
            py = float(mapped[0, 0, 1])
        else:
            # Fallback: linear scaling
            px = (x / half_w) * half_w + half_w
            py = (-y / half_h) * half_h + half_h
        
        overlay_points.append((px, py, designator, package, rotation))
    
    return overlay_points


# GUI Functions

def to_pil(img):
    """Convert numpy array to PIL Image."""
    if img is None:
        return None
    if img.ndim == 2:
        return Image.fromarray(img)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def launch_image_viewer(image_path, master=None, overlay_points=None, packages=None):
    """Launch Tkinter image viewer with zoom and overlay support."""
    if tk is None or Image is None or ImageTk is None:
        print("Tkinter/Pillow not available")
        return

    # Image loading helpers
    def load_image(path):
        try:
            return Image.open(path)
        except Exception as e:
            print(f"Could not load image: {path} ({e})")
            return None

    # Setup window
    owns_root = False
    if master is None:
        master = tk.Tk()
        owns_root = True

    window = master if owns_root else tk.Toplevel(master)
    window.title(f"PCB AOI — {os.path.basename(image_path)}")

    # Handle window close to exit app properly
    def on_window_close():
        if master is not None:
            master.destroy()
        else:
            window.destroy()
    window.protocol("WM_DELETE_WINDOW", on_window_close)

    # Load image
    pil_img = load_image(image_path)
    if pil_img is None:
        return

    # Calculate default zoom
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    scale = min(screen_w * 0.92 / pil_img.width, 
                screen_h * 0.82 / pil_img.height, 1.0)
    scale = max(scale, 0.1)
    zoom_state = {"scale": scale}

    # Overlay and grid settings
    overlay_enabled = tk.BooleanVar(value=True)
    grid_enabled = tk.BooleanVar(value=False)
    overlay_points = overlay_points if overlay_points is not None else []
    
    board_transform = None
    board_half_w = None
    board_half_h = None
    
    orig_img = None
    curr_img_arr = None
    curr_pil_img = pil_img

    def set_image(new_pil):
        nonlocal curr_img_arr, orig_img, curr_pil_img
        if new_pil is None:
            return
        
        curr_pil_img = new_pil
        try:
            arr = np.array(new_pil)
            if arr.ndim == 3 and arr.shape[2] == 3:
                curr_img_arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            elif arr.ndim == 3 and arr.shape[2] == 4:
                curr_img_arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
            else:
                curr_img_arr = arr
        except Exception:
            curr_img_arr = None

        if orig_img is None and curr_img_arr is not None:
            orig_img = curr_img_arr.copy()
        
        update_display()

    def update_display():
        scale = zoom_state["scale"]
        img = curr_img_arr.copy() if curr_img_arr is not None else None
        display_img = to_pil(img)

        if curr_img_arr is not None:
            if display_img is None:
                return
            
            # Resize using PIL
            new_size = (max(1, int(display_img.width * scale)),
                        max(1, int(display_img.height * scale)))
            resized = display_img.resize(new_size, Image.LANCZOS)
            
            # Convert to numpy array for OpenCV operations
            img_array = np.array(resized)

            global pixel_per_mm_scale, pcb_w
            pixel_per_mm_scale = (new_size[0]-1) / pcb_w
            
            # Draw overlay points using OpenCV
            if overlay_enabled.get():
                for pt in overlay_points:
                    if len(pt) < 2:
                        continue
                    cx, cy = int(pt[0] * scale), int(pt[1] * scale)
                    label = pt[2] if len(pt) >= 3 else None
                    
                    # Draw center crosshair
                    cv2.line(img_array, (cx-10, cy), (cx+10, cy), (255, 0, 0), 1)
                    cv2.line(img_array, (cx, cy-10), (cx, cy+10), (255, 0, 0), 1)
                    
                    # Draw component label
                    if label:
                        cv2.putText(img_array, str(label), (cx+12, cy-12),
                                    cv2.FONT_HERSHEY_SIMPLEX, max(0.25, 2*scale),
                                    (0, 0, 0), 3, cv2.LINE_AA)
                        cv2.putText(img_array, str(label), (cx+12, cy-12),
                                    cv2.FONT_HERSHEY_SIMPLEX, max(0.25, 2*scale),
                                    (255, 255, 255), 1, cv2.LINE_AA)

                    #Draw package outline if known
                    package = pt[3]
                    rotation = pt[4]
                    if package in PACKAGE_DIMENSIONS:
                        pkg_w, pkg_h = PACKAGE_DIMENSIONS[package]
                        #half_pkg_w = int(pkg_w * pixel_per_mm_scale /2 * scale)
                        #half_pkg_h = int(pkg_h * pixel_per_mm_scale /2 * scale)
                        
                        # Account for rotation when drawing package outline
                        center = (cx, cy)
                        size = (pkg_w * pixel_per_mm_scale * scale, pkg_h * pixel_per_mm_scale * scale)
                        angle = rotation
                        box = cv2.boxPoints((center, size, angle))
                        box = np.int0(box)

            
            # Convert back to PIL and then to PhotoImage
            resized_pil = Image.fromarray(img_array)
            tk_img = ImageTk.PhotoImage(resized_pil)


            
            # Draw grid
            if grid_enabled.get():
                if board_transform is not None and board_half_w is not None and board_half_h is not None:
                    draw_grid(tk_img)
                else:
                    cv2.putText(tk_img, "Grid: missing transform", (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            canvas.config(width=new_size[0], height=new_size[1])
            canvas.itemconfig(canvas_img, image=tk_img)
            canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))
            canvas.image = tk_img
        else:
            display_img = curr_pil_img

    def draw_grid(img):
        h, w = img.shape[:2]
        grid_color = (0, 255, 255)  # Yellow in BGR
        grid_spacing_mm = 10.0  # Strict 10mm grid spacing
        grid_alpha = 0.5  # 50% transparency

        # Create a transparent overlay for the grid
        overlay = img.copy()

        # Vertical grid lines at strict 10mm intervals
        x_positions = np.arange(
            np.ceil(-board_half_w / grid_spacing_mm) * grid_spacing_mm,
            board_half_w + grid_spacing_mm / 2,
            grid_spacing_mm,
        )
        for x_val in x_positions:
            pts = np.array(
                [[[x_val, -y_val]] for y_val in np.linspace(-board_half_h, board_half_h, 100)],
                dtype=np.float32,
            )
            mapped = cv2.perspectiveTransform(pts, board_transform).reshape(-1, 2).astype(int)
            for i in range(len(mapped) - 1):
                cv2.line(overlay, tuple(mapped[i]), tuple(mapped[i + 1]), grid_color, 2)

        # Horizontal grid lines at strict 10mm intervals
        y_positions = np.arange(
            np.ceil(-board_half_h / grid_spacing_mm) * grid_spacing_mm,
            board_half_h + grid_spacing_mm / 2,
            grid_spacing_mm,
        )
        for y_val in y_positions:
            pts = np.array(
                [[[x_val, -y_val]] for x_val in np.linspace(-board_half_w, board_half_w, 100)],
                dtype=np.float32,
            )
            mapped = cv2.perspectiveTransform(pts, board_transform).reshape(-1, 2).astype(int)
            for i in range(len(mapped) - 1):
                cv2.line(overlay, tuple(mapped[i]), tuple(mapped[i + 1]), grid_color, 2)

        # Blend the overlay with the original image at 50% transparency
        cv2.addWeighted(overlay, grid_alpha, img, 1 - grid_alpha, 0, img)

    def set_zoom(new_scale, center=None):
        new_scale = float(new_scale)
        old = zoom_state["scale"]
        zoom_state["scale"] = max(0.1, min(10.0, new_scale))
        
        # Update slider position
        if hasattr(zoom_slider, 'set'):
            zoom_slider.set(zoom_state["scale"])
        
        if center and old != zoom_state["scale"]:
            cx, cy, wx, wy = center
            ix, iy = cx / old, cy / old
            ncX, ncY = ix * zoom_state["scale"], iy * zoom_state["scale"]
            
            bbox = canvas.bbox(canvas_img)
            if bbox:
                cw, ch = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if cw > 0 and ch > 0:
                    fx = max(0, min(1, (ncX - wx) / cw))
                    fy = max(0, min(1, (ncY - wy) / ch))
                    canvas.xview_moveto(fx)
                    canvas.yview_moveto(fy)
        
        update_display()

    # Create UI
    control_frame = tk.Frame(window)
    control_frame.pack(fill="x", padx=4, pady=4)

    tk.Label(control_frame, text=f"Viewing: {os.path.basename(image_path)}").pack(side="left")
    
    tk.Checkbutton(control_frame, text="Overlay", variable=overlay_enabled,
                   command=update_display).pack(side="right", padx=4)
    tk.Checkbutton(control_frame, text="Grid", variable=grid_enabled,
                   command=update_display).pack(side="right", padx=4)
    
    tk.Button(control_frame, text="Zoom In", 
              command=lambda: set_zoom(zoom_state["scale"] * 1.2)).pack(side="right")
    tk.Button(control_frame, text="Zoom Out",
              command=lambda: set_zoom(zoom_state["scale"] / 1.2)).pack(side="right")

    zoom_slider = tk.Scale(control_frame, from_=0.1, to=10.0, orient="horizontal",
                           resolution=0.05, command=set_zoom, length=200)
    zoom_slider.set(scale)
    zoom_slider.pack(side="right", padx=4)

    # Canvas
    container = tk.Frame(window)
    container.pack(fill="both", expand=True)

    v_scroll = tk.Scrollbar(container, orient="vertical")
    h_scroll = tk.Scrollbar(container, orient="horizontal")
    v_scroll.pack(side="right", fill="y")
    h_scroll.pack(side="bottom", fill="x")

    canvas = tk.Canvas(container, bg="black", xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
    canvas.pack(fill="both", expand=True)
    v_scroll.config(command=canvas.yview)
    h_scroll.config(command=canvas.xview)
    canvas_img = canvas.create_image(0, 0, anchor="nw")

    # Mouse handling
    canvas.bind("<ButtonPress-1>", lambda e: canvas.scan_mark(e.x, e.y))
    canvas.bind("<B1-Motion>", lambda e: canvas.scan_dragto(e.x, e.y, gain=1))
    
    def on_mousewheel(event):
        factor = 1.2 if (event.delta > 0 or event.num == 4) else 1/1.2
        wx = event.x_root - canvas.winfo_rootx()
        wy = event.y_root - canvas.winfo_rooty()
        set_zoom(zoom_state["scale"] * factor, (canvas.canvasx(wx), canvas.canvasy(wy), wx, wy))

    window.bind_all("<MouseWheel>", on_mousewheel)
    window.bind_all("<Button-4>", on_mousewheel)
    window.bind_all("<Button-5>", on_mousewheel)
    window.bind_all("<Key>", lambda e: set_zoom(zoom_state["scale"] * 1.2) 
                   if e.keysym in ("plus", "equal", "=") else 
                   set_zoom(zoom_state["scale"] / 1.2) if e.keysym == "minus" else None)

    # Initial display
    set_image(pil_img)

    # Return interface
    def set_board_transform(t, hw, hh):
        nonlocal board_transform, board_half_w, board_half_h
        board_transform, board_half_w, board_half_h = t, hw, hh

    viewer = {
        "set_image": set_image,
        "set_board_transform": set_board_transform,
        "refresh": update_display,
    }

    if owns_root:
        window.mainloop()
    
    return viewer


def launch_mnt_viewer(mnt_path, master=None, components=None):
    """Launch component list viewer."""
    if ttk is None:
        return

    if components is None:
        components = parse_mnt_file(mnt_path)

    owns_root = False
    if master is None:
        master = tk.Tk()
        owns_root = True

    window = master if owns_root else tk.Toplevel(master)
    window.title(f"Components — {os.path.basename(mnt_path)}")

    frame = ttk.Frame(window, padding=8)
    frame.pack(fill="both", expand=True)

    style = ttk.Style(window)
    style.configure("Treeview", rowheight=32)

    columns = ["designator", "x", "y", "rotation", "value", "package"]
    tree = ttk.Treeview(frame, columns=columns, show="headings")

    for col in columns:
        tree.heading(col, text=col.capitalize())
        tree.column(col, width=120, anchor="center")

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscroll=vsb.set, xscroll=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    for comp in components:
        tree.insert("", "end", values=(
            comp["designator"], comp["x"], comp["y"], comp["rotation"],
            comp["value"], comp["package"]
        ))

    if owns_root:
        window.mainloop()


def launch_config_viewer(cfg_path, master=None):
    """Launch PCB config viewer."""
    if tk is None:
        return

    cfg = parse_pcb_config(cfg_path)
    width = cfg.get("pcb_width")
    height = cfg.get("pcb_height")

    if width is None or height is None:
        print(f"Invalid config: {cfg_path}")
        return

    owns_root = False
    if master is None:
        master = tk.Tk()
        owns_root = True

    window = master if owns_root else tk.Toplevel(master)
    window.title(f"PCB Config — {os.path.basename(cfg_path)}")

    frame = tk.Frame(window, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="PCB dimensions", font=(None, 12, "bold")).pack(anchor="w")
    tk.Label(frame, text=f"Width: {width:.2f} mm").pack(anchor="w", pady=(8, 0))
    tk.Label(frame, text=f"Height: {height:.2f} mm").pack(anchor="w")

    if owns_root:
        window.mainloop()


# Main Processing

def main():
    print("apertus° PCB inspector")
    
    if len(sys.argv) < 2:
        print("Usage: python pcb_processing.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    
    # Setup tkinter
    root = None
    if tk is not None and Image is not None:
        root = tk.Tk()
        root.withdraw()

    overlay_points = []
    image_viewer = None
    components = []
    base = ""
    board_cfg = {}

    # Determine base path for companion files
    if image_path.lower().endswith(".mnt"):
        base = os.path.splitext(os.path.basename(image_path))[0]
        mnt_dir = os.path.dirname(image_path) or "."
        # Parse .mnt first
        components = parse_mnt_file(image_path)
        launch_mnt_viewer(image_path, master=root, components=components)
        
        # Find image
        for ext in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
            img_candidate = os.path.join(mnt_dir, base + ext)
            if os.path.exists(img_candidate):
                image_path = img_candidate
                break
    else:
        base = os.path.splitext(image_path)[0]


    # Load companion files
    mnt_path = base + ".mnt"
    cfg_path = base + ".cfg"

    # Parse .mnt if not already done
    if os.path.exists(mnt_path) and not components:
        components = parse_mnt_file(mnt_path)
        launch_mnt_viewer(mnt_path, master=root, components=components)
    
    # Parse .cfg
    if os.path.exists(cfg_path):
        board_cfg = parse_pcb_config(cfg_path)
        launch_config_viewer(cfg_path, master=root)

    # Launch packages config viewer
    if create_packages_config_gui is not None:
        create_packages_config_gui(master=root)

    # Launch image viewer
    image_viewer = launch_image_viewer(image_path, master=root, overlay_points=overlay_points)

    # Process image
    img_ref = cv2.imread(image_path, 1)
    img_gray = cv2.cvtColor(img_ref, cv2.COLOR_RGB2GRAY)
    template = cv2.imread(fiducialTemplate, 0)

    print(f"Image: {img_gray.shape[1]}x{img_gray.shape[0]}")

    # Find fiducials
    global fiducialPositions
    fiducialPositions = find_all_fiducials(img_gray, template)
    
    print("Detected fiducials in image:")
    for i, pos in enumerate(fiducialPositions):
        print(f"  {i+1}: ({pos[0]:.0f}, {pos[1]:.0f})")

    # Apply transform
    img_warped, transform, warped_w, warped_h = apply_perspective_transform(
        img_ref, fiducialPositions, 
        pcb_width=board_cfg.get("pcb_width"), 
        pcb_height=board_cfg.get("pcb_height"), 
        fiducial_positions_mm=fiducialBoardPositions
    )
    print(f"Warped: {warped_w}x{warped_h}")

    # Compute component overlay positions
    global pcb_w, pcb_h
    pcb_w = board_cfg.get("pcb_width")
    pcb_h = board_cfg.get("pcb_height")

    if components and fiducialBoardPositions and pcb_w and pcb_h:
        half_w, half_h = pcb_w / 2, pcb_h / 2
        
        M = compute_board_to_image_transform(pcb_w, pcb_h, warped_w, warped_h)
        global pixel_per_mm_scale
        pixel_per_mm_scale = (warped_w-1)/pcb_w
        print(f"PCB: {pcb_w}x{pcb_h} mm, Scale: {(warped_w-1)/pcb_w:.2f} px/mm")
        
        overlay_points.extend(transform_component_positions(components, M, warped_w, warped_h))
        print(f"Generated {len(overlay_points)} overlay points")

        # Setup viewer transform
        if image_viewer:
            image_viewer["set_board_transform"](M, half_w, half_h)

    # Show warped image
    if image_viewer:
        display_img = to_pil(img_warped)
        image_viewer["set_image"](display_img)

    if root:
        root.mainloop()


if __name__ == '__main__':
    main()