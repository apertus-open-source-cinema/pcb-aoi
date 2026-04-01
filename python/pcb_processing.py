#!/usr/bin/python
"""
PCB AOI (Automated Optical Inspection) Processing Script

This script processes PCB images, detects fiducials, applies perspective
transformations, and overlays component positions.
"""

import sys
import os

# Check for required dependencies before proceeding
def _check_startup_dependencies():
    pip_missing = []
    try:
        import numpy
    except ImportError:
        pip_missing.append("numpy")
    try:
        import cv2
    except ImportError:
        pip_missing.append("opencv-python")
    try:
        from PIL import Image
    except ImportError:
        pip_missing.append("pillow")
    
    tk_missing = False
    try:
        import tkinter
    except ImportError:
        tk_missing = True

    if pip_missing or tk_missing:
        print("\n[!] Error: Missing core dependencies for PCB AOI Inspector")
        
        if pip_missing:
            print(f"The following Python packages are missing: {', '.join(pip_missing)}")
            print(f"You can install them using: pip install {' '.join(pip_missing)}")
            
        if tk_missing:
            print("\nThe 'tkinter' module is missing.")
            if sys.platform.startswith('linux'):
                print("On Linux, you can install it using: sudo apt install python3-tk")
            else:
                print("Please reinstall Python and ensure 'tcl/tk and IDLE' is checked in the installer.")
                
        sys.exit(1)

_check_startup_dependencies()

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

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from window_manager import apply_saved_geometry, set_window_geometry


# Global Variables
fiducialTemplate = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'fiducial.tif')
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
    
    return positions
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


def parse_pcb_pads_file(path):
    """Parse pad location file.

    Returns:
        List of pad dicts with keys: component, pin, x, y
    """
    pads = []
    if not os.path.exists(path):
        return pads

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(",")
            if len(parts) < 4:
                continue

            try:
                component = parts[0].strip()
                pin = int(parts[1].strip())
                x = float(parts[2].strip())
                y = float(parts[3].strip())
                pads.append({"component": component, "pin": pin, "x": x, "y": y})
            except ValueError:
                continue
    return pads

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


def transform_pad_positions(pads, transform_matrix, img_width, img_height):
    """Transform pad positions from board coords to image pixels."""
    transformed_pads = []
    half_w = img_width / 2.0
    half_h = img_height / 2.0

    for pad in pads:
        component = pad.get("component", "")
        pin = pad.get("pin", 0)
        x, y = pad.get("x"), pad.get("y")
        if x is None or y is None:
            continue

        # Convert board coords to image coords (flip y)
        pt = np.array([[[x, -y]]], dtype=np.float32)

        mapped = cv2.perspectiveTransform(pt, transform_matrix)
        px = float(mapped[0, 0, 0])
        py = float(mapped[0, 0, 1])

        transformed_pads.append((px, py, component, pin))

    return transformed_pads

# GUI Functions

def to_pil(img):
    """Convert numpy array to PIL Image."""
    if img is None:
        return None
    if img.ndim == 2:
        return Image.fromarray(img)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def launch_image_viewer(image_path, master=None, overlay_points=None, pad_locations=None):
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

    # Apply saved geometry
    apply_saved_geometry(window, "ImageViewer")

    # Handle window close to exit app properly
    def on_window_close():
        if master is not None:
            master.destroy()
        else:
            window.destroy()
    window.protocol("WM_DELETE_WINDOW", on_window_close)

    # Save geometry on destruction
    window.bind("<Destroy>", lambda e: set_window_geometry(window, "ImageViewer") if e.widget == window else None)

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
    pads_enabled = tk.BooleanVar(value=False) # New: Display Pads checkbox
    overlay_points = overlay_points if overlay_points is not None else []
    overlay_map = {pt[2]: pt for pt in overlay_points if len(pt) >= 3}
    
    board_transform = None
    board_half_w = None
    board_half_h = None
    
    orig_img = None
    curr_img_arr = None
    pads_data = pad_locations if pad_locations is not None else [] # Store transformed pad locations
    curr_pil_img = pil_img
    highlighted_designator = None # Added for component highlighting
    
    # Comparison mode settings (must be defined before nested functions)
    comparison_mode = tk.BooleanVar(value=False)
    comparison_results = []
    
    # Interface dictionary (defined early for closure access)
    viewer = {}

    status_var = tk.StringVar()

    def update_status_bar(event=None):
        scale = zoom_state["scale"]
        txt = f"Zoom: {scale*100:.1f}%"
        
        if event and board_transform is not None:
            # Mouse pos in canvas space (accounts for scrolling)
            mx = canvas.canvasx(event.x)
            my = canvas.canvasy(event.y)
            
            # Map zoomed pixels back to warped image pixels
            px, py = mx / scale, my / scale
            
            try:
                # board_transform maps (x, -y) -> (px, py)
                # Inverse maps (px, py) -> (x, -y)
                success, M_inv = cv2.invert(board_transform)
                if success:
                    pt = np.array([[[px, py]]], dtype=np.float32)
                    res = cv2.perspectiveTransform(pt, M_inv)
                    bx, by_neg = res[0][0]
                    txt += f" | Cursor: X={bx:.2f} mm, Y={-by_neg:.2f} mm"
            except Exception:
                pass
        status_var.set(txt)

    def set_highlight(designator):
        nonlocal highlighted_designator
        highlighted_designator = designator
        
        # Auto-center on the selected component
        target_zoom_scale = 1.0 # As per previous request, zoom to 100%
        pt = next((p for p in overlay_points if len(p) >= 3 and p[2] == designator), None)
        if pt:
            # First, set the new zoom level. This will also trigger update_display.
            set_zoom(target_zoom_scale)

            # Now, after the image has been resized due to the new zoom,
            # calculate and apply scroll positions to center the component.
            scale = zoom_state["scale"] # This will now be target_zoom_scale
            cx_scaled, cy_scaled = pt[0] * scale, pt[1] * scale

            window.update_idletasks()
            v_w, v_h = canvas.winfo_width(), canvas.winfo_height()
            bbox = canvas.bbox(canvas_img)
            if bbox:
                t_w, t_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if t_w > 0 and t_h > 0:
                    # Center the component by setting the scroll position
                    canvas.xview_moveto(max(0, min(1, (cx_scaled - v_w / 2) / t_w)))
                    canvas.yview_moveto(max(0, min(1, (cy_scaled - v_h / 2) / t_h)))
        update_display() # Ensure display is updated after highlight change

    def set_image(new_pil):
        nonlocal curr_img_arr, orig_img, curr_pil_img
        if new_pil is None:
            return
        
        curr_pil_img = new_pil
        try:
            arr = np.asarray(new_pil)
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
        update_status_bar()
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
            img_array = np.asarray(resized)

            global pixel_per_mm_scale, pcb_w
            pixel_per_mm_scale = (new_size[0]-1) / pcb_w
            #print(f"Pixel/mm scale: {pixel_per_mm_scale:.2f} px/mm")
            
            # Create results map for fast lookup
            results_map = {}
            results = viewer.get("comparison_results", [])
            if results:
                for res in results:
                    if len(res) >= 6:
                        results_map[res[0]] = res[5]
            
            # Draw overlay points using OpenCV
            if overlay_enabled.get():
                for pt in overlay_points:
                    if len(pt) < 2:
                        continue
                    cx, cy = int(pt[0] * scale), int(pt[1] * scale)
                    label = pt[2] if len(pt) >= 3 else None
                    
                    # Draw center crosshair
                    crosshair_size = 5
                    cv2.line(img_array, (cx-crosshair_size, cy), (cx+crosshair_size, cy), (180, 180, 180), 1)
                    cv2.line(img_array, (cx, cy-crosshair_size), (cx, cy+crosshair_size), (180, 180, 180), 1)
                    
                    # Draw component label
                    if label:
                        cv2.putText(img_array, str(label), (cx+12, cy-12),
                                    cv2.FONT_HERSHEY_SIMPLEX, max(0.25, 0.5),
                                    (0, 0, 0), 3, cv2.LINE_AA)
                        cv2.putText(img_array, str(label), (cx+12, cy-12),
                                    cv2.FONT_HERSHEY_SIMPLEX, max(0.25, 0.5),
                                    (255, 255, 255), 1, cv2.LINE_AA)

                    #Draw package outline if known
                    package = pt[3]
                    rotation = pt[4]
                    if package in PACKAGE_DIMENSIONS:
                        pkg_w, pkg_h = PACKAGE_DIMENSIONS[package]
                        center = (cx, cy)
                        size = (pkg_w * pixel_per_mm_scale, pkg_h * pixel_per_mm_scale)
                        angle = rotation
                        box = cv2.boxPoints((center, size, angle))
                        box = np.intp(box)
                        
                        # Determine color based on match value
                        if label in results_map:
                            max_val = results_map[label]
                            if max_val > 0.8:
                                current_outline_color = (0, 255, 0) # Green for match
                                current_outline_thickness = 1
                                cv2.drawContours(img_array, [box], 0, current_outline_color, current_outline_thickness)      
                            else:
                                current_outline_color = (255, 0, 0) # Red for mismatch
                                current_outline_thickness = 2
                                cv2.drawContours(img_array, [box], 0, current_outline_color, current_outline_thickness)
                        else:
                            # Draw bold highlight if this component is selected in the list
                            if label == highlighted_designator:
                                cv2.drawContours(img_array, [box], 0, (255, 0, 255), 4) # Magenta, thicker
                            else:
                                # reference mode
                                color = (200, 200, 200) # light grey
                                cv2.drawContours(img_array, [box], 0, color, 1)
            
            # Draw grid
                    elif label == highlighted_designator:
                        # Fallback highlight circle if package dimensions are unknown
                        cv2.circle(img_array, (cx, cy), int(15 * scale), (255, 0, 255), 3) # Magenta circle
            if grid_enabled.get():
                if board_transform is not None and board_half_w is not None and board_half_h is not None:
                    draw_grid(img_array)
                else:
                    cv2.putText(img_array, "Grid: missing transform", (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # Draw pads
            if pads_enabled.get() and pads_data:
                for px, py, comp, pin in pads_data:
                    cx, cy = int(px * scale), int(py * scale)
                    # Draw a small circle for each pad
                    cv2.circle(img_array, (cx, cy), 3, (255, 255, 0), -1) # Yellow circle, filled
                    #cv2.putText(img_array, f"{comp}.{pin}", (cx + 5, cy - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)

            # Convert back to PIL and then to PhotoImage
            resized_pil = Image.fromarray(img_array)
            tk_img = ImageTk.PhotoImage(resized_pil)
            
            canvas.config(width=new_size[0], height=new_size[1])
            canvas.itemconfig(canvas_img, image=tk_img)
            canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))
            canvas.image = tk_img
        else:
            display_img = curr_pil_img

    def draw_grid(img):
        h, w = img.shape[:2]
        grid_color = (255, 255, 0)  # Yellow in BGR
        grid_spacing_mm = 10.0  # Strict 10mm grid spacing
        grid_alpha = 0.5  # 50% transparency
        scale = zoom_state["scale"]

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
            mapped = cv2.perspectiveTransform(pts, board_transform).reshape(-1, 2)
            mapped = (mapped * scale).astype(int)
            for i in range(len(mapped) - 1):
                cv2.line(overlay, tuple(mapped[i]), tuple(mapped[i + 1]), grid_color, 1)

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
            mapped = cv2.perspectiveTransform(pts, board_transform).reshape(-1, 2)
            mapped = (mapped * scale).astype(int)
            for i in range(len(mapped) - 1):
                cv2.line(overlay, tuple(mapped[i]), tuple(mapped[i + 1]), grid_color, 1)

        # Blend the overlay with the original image at 50% transparency
        cv2.addWeighted(overlay, grid_alpha, img, 1 - grid_alpha, 0, img)

    def update_comparison_display():
        """Update display with comparison results."""
        nonlocal curr_img_arr

        if not comparison_mode.get() or orig_img is None:
            return
        
        comparison_results = viewer.get("comparison_results", [])
        
        # Start from original clean image
        display = orig_img.copy()
        
        # Draw comparison results
        for result in comparison_results:
            # Unpack result (handle potential variable length for backward compatibility)
            if len(result) >= 9:
                designator, match_status, diff_x, diff_y, diff_area, max_val, _, _, _ = result
            else:
                designator, match_status, diff_x, diff_y, diff_area = result
                max_val = 0
            
            # Color based on match status
            if match_status:
                color = (0, 255, 0)  # Green for match
                status_text = "MATCH"
            else:
                color = (0, 0, 255)  # Red for mismatch
                status_text = "MISMATCH"
            
            if designator in overlay_map:
                pt = overlay_map[designator]
                cx, cy = int(pt[0]), int(pt[1])
                package = pt[3]
                rotation = pt[4]

                # Draw package outline if known
                if package in PACKAGE_DIMENSIONS:
                    pkg_w, pkg_h = PACKAGE_DIMENSIONS[package]
                    size = (pkg_w * pixel_per_mm_scale, pkg_h * pixel_per_mm_scale)
                    box = cv2.boxPoints(((cx, cy), size, rotation))
                    box = np.intp(box)
                    cv2.drawContours(display, [box], 0, color, 2)
                else:
                    cv2.circle(display, (cx, cy), 15, color, 2)
                
                # Draw status text
                cv2.putText(display, f"{max_val:.2f}", (cx + 10, cy - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            else:
                # Fallback if position lost
                cx, cy = int(display.shape[1] // 2), int(display.shape[0] // 2)
                cv2.putText(display, f"{designator}?", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        
        curr_img_arr = display
        update_display()

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

    def zoom_fit():
        """Adjust zoom to fit the image within the current canvas area."""
        if curr_pil_img is None:
            return
        window.update_idletasks()
        v_w, v_h = canvas.winfo_width(), canvas.winfo_height()
        if v_w > 1 and v_h > 1:
            img_w, img_h = curr_pil_img.size
            set_zoom(min(v_w / img_w, v_h / img_h))

    # Create UI
    control_frame = tk.Frame(window)
    control_frame.pack(fill="x", padx=4, pady=4)

    tk.Label(control_frame, text=f"Viewing: {os.path.basename(image_path)}").pack(side="left")
    
    tk.Checkbutton(control_frame, text="Overlay", variable=overlay_enabled,
                   command=update_display).pack(side="right", padx=4)
    tk.Checkbutton(control_frame, text="Display Pads", variable=pads_enabled,
                   command=update_display).pack(side="right", padx=4) # New checkbox
    tk.Checkbutton(control_frame, text="10mm Grid", variable=grid_enabled,
                   command=update_display).pack(side="right", padx=4)
    
    tk.Button(control_frame, text="Zoom +",
              command=lambda: set_zoom(zoom_state["scale"] * 1.2)).pack(side="right")
    tk.Button(control_frame, text="Zoom -",
              command=lambda: set_zoom(zoom_state["scale"] / 1.2)).pack(side="right")
    tk.Button(control_frame, text="Zoom fit",
              command=zoom_fit).pack(side="right", padx=4)

    zoom_slider = tk.Scale(control_frame, from_=0.1, to=10.0, orient="horizontal",
                           resolution=0.05, command=set_zoom, length=200)
    zoom_slider.set(scale)
    zoom_slider.pack(side="right", padx=4)

    # Status bar
    status_bar = tk.Label(window, textvariable=status_var, bd=1, relief=tk.SUNKEN, anchor="w", padx=5)
    status_bar.pack(side="bottom", fill="x")

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
    canvas.bind("<Motion>", update_status_bar)
    
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

    def set_comparison_mode(enabled):
        nonlocal comparison_mode
        comparison_mode.set(enabled)
        if enabled:
            update_comparison_display()
        else:
            if orig_img is not None:
                curr_img_arr = orig_img.copy()
                update_display()

    def set_pad_locations(new_pads):
        nonlocal pads_data
        pads_data = new_pads
        update_display()

    viewer.update({
        "set_image": set_image,
        "set_board_transform": set_board_transform,
        "set_comparison_mode": set_comparison_mode,
        "refresh": update_display,
        "set_highlight": set_highlight, # Added to viewer interface
        "set_pad_locations": set_pad_locations, # New: Set pad locations
        "comparison_mode": comparison_mode,
    })

    if owns_root:
        window.mainloop()
    
    return viewer


def launch_mnt_viewer(mnt_path, master=None, components=None, image_viewer=None): # Added image_viewer parameter
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

    # Apply saved geometry
    apply_saved_geometry(window, "MNTViewer")

    frame = ttk.Frame(window, padding=8)
    frame.pack(fill="both", expand=True)

    style = ttk.Style(window)
    style.configure("Treeview", rowheight=32)

    columns = ["designator", "show", "x", "y", "rotation", "value", "package"]
    tree = ttk.Treeview(frame, columns=columns, show="headings")

    for col in columns:
        header_text = "Show" if col == "show" else col.capitalize()
        width = 80 if col == "show" else 120
        tree.heading(col, text=header_text)
        tree.column(col, width=width, anchor="center")

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
            comp["designator"], "[ 🔍 Show ]", comp["x"], comp["y"], comp["rotation"],
            comp["value"], comp["package"]
        ))

    def on_tree_click(event):
        """Handle clicking the 'Show' button column."""
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            item = tree.identify_row(event.y)
            if item and column == "#2": # The 'show' column is second
                designator = tree.item(item)['values'][0]
                if image_viewer:
                    image_viewer["set_highlight"](designator)

    def on_motion(event):
        """Update cursor to hand when hovering over the Show 'button'."""
        region = tree.identify_region(event.x, event.y)
        column = tree.identify_column(event.x)
        if region == "cell" and column == "#2":
            tree.configure(cursor="hand2")
        else:
            tree.configure(cursor="")

    tree.bind("<Button-1>", on_tree_click)
    tree.bind("<Motion>", on_motion)

    def handle_closing():
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", handle_closing)

    # Ensure geometry is saved even if the parent destroys this window
    window.bind("<Destroy>", lambda e: set_window_geometry(window, "MNTViewer") if e.widget == window else None)

    if owns_root:
        window.mainloop()


def launch_comparison_table(comparison_results, master=None):
    """Launch comparison results table with images."""
    if tk is None or Image is None or ImageTk is None:
        print("Tkinter/Pillow not available")
        return

    # Sort results: Mismatches (False) first, then Matches (True)
    sorted_results = sorted(comparison_results, key=lambda x: x[1])

    owns_root = False
    if master is None:
        master = tk.Tk()
        owns_root = True

    window = master if owns_root else tk.Toplevel(master)
    window.title("Comparison Results")
    window.geometry("1000x600")

    # Apply saved geometry
    apply_saved_geometry(window, "ComparisonTable")

    # Control frame
    control_frame = ttk.Frame(window)
    control_frame.pack(side="top", fill="x", padx=5, pady=5)

    # Create container for canvas and scrollbar
    container = ttk.Frame(window)
    container.pack(fill="both", expand=True)
    
    canvas = tk.Canvas(container)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def on_canvas_configure(event):
        canvas.itemconfig(window_id, width=event.width)
    canvas.bind("<Configure>", on_canvas_configure)

    # Keep references to images
    window.image_refs = []
    
    # Current width state (pixels)
    current_width = [40]

    def populate_table():
        # Clear existing
        for widget in scrollable_frame.winfo_children():
            widget.destroy()
        window.image_refs.clear()

        # Headers
        headers = ["Designator", "Package", "Match Val", "Ref Image", "Cmp Image"]
        for i, h in enumerate(headers):
            ttk.Label(scrollable_frame, text=h, font=("Arial", 10, "bold"), anchor="center").grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            scrollable_frame.columnconfigure(i, weight=1)

        for i, result in enumerate(sorted_results):
            # Unpack tuple (designator, match_status, diff_x, diff_y, diff_area, max_val, ref_crop, sec_crop, package)
            if len(result) < 9: continue
            designator, match_status, _, _, _, max_val, ref_crop, sec_crop, package = result
            
            row = i + 1
            fg_color = "green" if match_status else "red"
            
            ttk.Label(scrollable_frame, text=designator, anchor="center").grid(row=row, column=0, padx=5, pady=5, sticky="ew")
            ttk.Label(scrollable_frame, text=package, anchor="center").grid(row=row, column=1, padx=5, pady=5, sticky="ew")
            ttk.Label(scrollable_frame, text=f"{max_val:.3f}", foreground=fg_color, anchor="center").grid(row=row, column=2, padx=5, pady=5, sticky="ew")

            def create_photo(crop):
                if crop is None or crop.size == 0: return None
                h, w = crop.shape[:2]
                if w == 0: return None
                target_w = current_width[0]
                scale = target_w / w
                resized = cv2.resize(crop, (target_w, int(h*scale)), interpolation=cv2.INTER_NEAREST)
                return ImageTk.PhotoImage(Image.fromarray(resized))

            ref_photo = create_photo(ref_crop)
            if ref_photo:
                l = ttk.Label(scrollable_frame, image=ref_photo, anchor="center")
                l.grid(row=row, column=3, padx=5, pady=5, sticky="ew")
                window.image_refs.append(ref_photo)

            sec_photo = create_photo(sec_crop)
            if sec_photo:
                l = ttk.Label(scrollable_frame, image=sec_photo, anchor="center")
                l.grid(row=row, column=4, padx=5, pady=5, sticky="ew")
                window.image_refs.append(sec_photo)

    def change_size(delta):
        current_width[0] = max(10, min(300, current_width[0] + delta))
        populate_table()

    ttk.Button(control_frame, text="Increase Size (+)", command=lambda: change_size(20)).pack(side="left", padx=5)
    ttk.Button(control_frame, text="Decrease Size (-)", command=lambda: change_size(-20)).pack(side="left", padx=5)

    def handle_closing():
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", handle_closing)

    # Ensure geometry is saved even if the parent destroys this window
    window.bind("<Destroy>", lambda e: set_window_geometry(window, "ComparisonTable") if e.widget == window else None)

    populate_table()

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

    # Apply saved geometry
    apply_saved_geometry(window, "ConfigViewer")

    frame = tk.Frame(window, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="PCB dimensions", font=(None, 12, "bold")).pack(anchor="w")
    tk.Label(frame, text=f"Width: {width:.2f} mm").pack(anchor="w", pady=(8, 0))
    tk.Label(frame, text=f"Height: {height:.2f} mm").pack(anchor="w")

    def handle_closing():
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", handle_closing)

    # Ensure geometry is saved even if the parent destroys this window
    window.bind("<Destroy>", lambda e: set_window_geometry(window, "ConfigViewer") if e.widget == window else None)

    if owns_root:
        window.mainloop()

def process_image_pipeline(image_path, fid_template, board_cfg, fiducial_pos_mm):
    """Load image, detect fiducials, and apply perspective transform."""
    img_color = cv2.imread(image_path, 1)
    if img_color is None:
        print(f"Failed to load image: {image_path}")
        return None, None, None, None, None, None

    img_gray = cv2.cvtColor(img_color, cv2.COLOR_RGB2GRAY)
    
    # Find fiducials
    detected_fiducials = find_all_fiducials(img_gray, fid_template)
    
    print(f"Detected fiducials in {os.path.basename(image_path)}:")
    for i, pos in enumerate(detected_fiducials):
        print(f"  {i+1}: ({pos[0]:.0f}, {pos[1]:.0f})")
    
    # Apply transform
    img_warped, transform, w, h = apply_perspective_transform(
        img_color, detected_fiducials,
        pcb_width=board_cfg.get("pcb_width"),
        pcb_height=board_cfg.get("pcb_height"),
        fiducial_positions_mm=fiducial_pos_mm
    )
    return img_color, img_gray, detected_fiducials, img_warped, transform, w, h

# Main Processing

def main():
    print("apertus° PCB inspector")
    
    if len(sys.argv) < 2:
        print("Usage: python pcb_processing.py <image_path> [second_image_path]")
        sys.exit(1)

    image_path = sys.argv[1]
    second_image_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Setup tkinter
    root = None
    if tk is not None and Image is not None:
        root = tk.Tk()
        root.withdraw()

    overlay_points = []
    image_viewer = None
    components = []
    pad_locations = [] # New: Store raw pad locations
    transformed_pad_locations = [] # New: Store transformed pad locations
    base = ""
    board_cfg = {}

    # Determine base path for companion files
    if image_path.lower().endswith(".mnt"):
        base = os.path.splitext(image_path)[0]
        mnt_dir = os.path.dirname(image_path) or "."
        # Parse .mnt first
        components = parse_mnt_file(image_path)
        
        # Find image
        for ext in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
            img_candidate = os.path.join(mnt_dir, base + ext)
            if os.path.exists(img_candidate):
                image_path = img_candidate
                break
    else:
        base = os.path.splitext(image_path)[0]

    # Load pad locations if .csv exists
    pads_path = base + ".csv"
    if os.path.exists(pads_path):
        pad_locations = parse_pcb_pads_file(pads_path)
        print(f"Found {len(pad_locations)} pads in {pads_path}")


    # Load companion files
    mnt_path = base + ".mnt"
    cfg_path = base + ".cfg"

    # Parse .mnt if not already done
    if os.path.exists(mnt_path) and not components:
        components = parse_mnt_file(mnt_path)
    
    # Parse .cfg
    if os.path.exists(cfg_path):
        board_cfg = parse_pcb_config(cfg_path)
        launch_config_viewer(cfg_path, master=root)

    # Launch image viewer
    image_viewer = launch_image_viewer(image_path, master=root, overlay_points=overlay_points, pad_locations=[]) # Pass empty list initially

    # Launch packages config viewer with a refresh callback for the image viewer
    if create_packages_config_gui is not None:
        def on_pkg_change():
            if image_viewer:
                image_viewer["refresh"]()
        create_packages_config_gui(master=root, components=components, on_change=on_pkg_change)

    # Launch component list viewer with image_viewer link
    if components:
        launch_mnt_viewer(mnt_path, master=root, components=components, image_viewer=image_viewer)

    # Process image
    template = cv2.imread(fiducialTemplate, 0)
    
    # Use global fiducialPositions for the first image as it's used elsewhere if needed
    global fiducialPositions
    img_ref, _, fiducialPositions, img_warped, transform, warped_w, warped_h = process_image_pipeline(
        image_path, template, board_cfg, fiducialBoardPositions
    )
    img_warped_gray = cv2.cvtColor(img_warped, cv2.COLOR_RGB2GRAY)
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

        if pad_locations: # If raw pad data was loaded
            transformed_pad_locations = transform_pad_positions(pad_locations, M, warped_w, warped_h)
            print(f"Generated {len(transformed_pad_locations)} transformed pad locations")

        # Setup viewer transform
        if image_viewer:
            image_viewer["set_board_transform"](M, half_w, half_h)
            image_viewer["set_pad_locations"](transformed_pad_locations) # Update pad locations in viewer

    # Process second image for comparison if provided
    if second_image_path and os.path.exists(second_image_path):
        print(f"\nProcessing comparison image: {second_image_path}")
        
        # Use pipeline for second image
        _, _, _, img_second_warped, transform_second, warped_w_second, warped_h_second = process_image_pipeline(
            second_image_path, template, board_cfg, fiducialBoardPositions
        )

        if img_second_warped is not None:
            img_second_warped_gray = cv2.cvtColor(img_second_warped, cv2.COLOR_RGB2GRAY)
            
            # Compare components
            if components and pcb_w and pcb_h:
                
                # Transform component positions for second image
                M_second = compute_board_to_image_transform(pcb_w, pcb_h, warped_w_second, warped_h_second)
                overlay_points_second = transform_component_positions(components, M_second, warped_w_second, warped_h_second)
                
                # Compare each component using template matching
                comparison_results = []
                # Template matching parameters
                MATCH_THRESHOLD = 0.8  # for TM_CCOEFF_NORMED
                
                print(f"Comparing components between images with match threshold {MATCH_THRESHOLD}:")

                debug_dir = "debug_crops"
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)

                for i, (ref_pt, comp_pt) in enumerate(zip(overlay_points, overlay_points_second)):
                    if len(ref_pt) >= 5 and len(comp_pt) >= 5:
                        designator = ref_pt[2]
                        
                        if designator.startswith("FID"):
                            continue  # Skip fiducials in comparison

                        # skip if package dimensions are zero
                        if (comp_pt[3] not in PACKAGE_DIMENSIONS) or (PACKAGE_DIMENSIONS[comp_pt[3]] == (0, 0)):
                            continue

                        ref_x, ref_y = int(ref_pt[0]), int(ref_pt[1])
                        comp_x, comp_y = int(comp_pt[0]), int(comp_pt[1])

                        # Calculate template size based on package
                        package = ref_pt[3]
                        rotation = ref_pt[4]
                        
                        template = None
                        sec_crop = None
                        t_w, t_h = 20, 20  # Default size
                        
                        if package in PACKAGE_DIMENSIONS:
                            pkg_w, pkg_h = PACKAGE_DIMENSIONS[package]
                            
                            MARGIN = 1.5 #50% margin to account for slight misalignments
                            
                            # Calculate size in pixels
                            px_w = pkg_w * pixel_per_mm_scale * MARGIN
                            px_h = pkg_h * pixel_per_mm_scale * MARGIN
                            
                            # Swap dimensions if rotated approx 90 degrees
                            if 45 < (abs(rotation) % 180) < 135:
                                px_w, px_h = px_h, px_w
                            
                            t_w, t_h = int(px_w), int(px_h)
                            # Ensure minimum size
                            t_w = max(t_w, 10)
                            t_h = max(t_h, 10)
                        
                        half_w = t_w // 2
                        half_h = t_h // 2
                        
                        # Extract template from reference warped grayscale image
                        # Check bounds
                        if (ref_y - half_h < 0) or (ref_y + half_h >= img_warped_gray.shape[0]) or \
                        (ref_x - half_w < 0) or (ref_x + half_w >= img_warped_gray.shape[1]):
                            # Out of bounds, cannot extract template
                            match_status = False
                            diff_x = 0
                            diff_y = 0
                            max_val = 0
                        else:
                            template = img_warped_gray[ref_y - half_h:ref_y + half_h, ref_x - half_w:ref_x + half_w]
                            
                            # Save debug images
                            cv2.imwrite(os.path.join(debug_dir, f"{designator}_ref.png"), template)
                            
                            # Extract corresponding crop from second image for debug
                            if (comp_y - half_h >= 0) and (comp_y + half_h < img_second_warped_gray.shape[0]) and \
                               (comp_x - half_w >= 0) and (comp_x + half_w < img_second_warped_gray.shape[1]):
                                sec_crop = img_second_warped_gray[comp_y - half_h:comp_y + half_h, comp_x - half_w:comp_x + half_w]
                                cv2.imwrite(os.path.join(debug_dir, f"{designator}_sec.png"), sec_crop)

                            # Perform template matching on second warped grayscale image
                            result = cv2.matchTemplate(sec_crop, template, cv2.TM_CCOEFF_NORMED)
                            _, max_val, _, max_loc = cv2.minMaxLoc(result)
                            # Calculate center of matched template in second image
                            matched_center_x = max_loc[0] + half_w
                            matched_center_y = max_loc[1] + half_h
                            # Calculate differences between matched position and expected position
                            diff_x = abs(matched_center_x - comp_x)
                            diff_y = abs(matched_center_y - comp_y)
                            # Determine match status based on match value
                            match_status = (max_val > MATCH_THRESHOLD) 
                        
                        diff_area = diff_x * diff_y  # maintain same format as before
                        
                        comparison_results.append((
                            designator, match_status, diff_x, diff_y, diff_area,
                            max_val, template, sec_crop, package
                        ))

                        if (max_val < MATCH_THRESHOLD):
                            print(f"Component {designator}: {'MATCH' if match_status else 'MISMATCH'} (Δx={diff_x:.2f}, Δy={diff_y:.2f}, match_val={max_val:.2f})")
                
                # Store comparison results in viewer
                if image_viewer:
                    image_viewer["comparison_results"] = comparison_results
                    image_viewer["set_comparison_mode"](False)  # Start in reference mode
                    
                if comparison_results:
                     launch_comparison_table(comparison_results, master=root)

    # Show warped image
    if image_viewer:
        display_img = to_pil(img_warped)
        image_viewer["set_image"](display_img)

    if root:
        root.mainloop()


if __name__ == '__main__':
    main()