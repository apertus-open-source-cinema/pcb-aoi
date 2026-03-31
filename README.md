# PCB AOI Inspector

The **PCB AOI (Automated Optical Inspection) Inspector** is a software tool designed to assist in the validation and inspection of Printed Circuit Boards (PCBs). It utilizes computer vision to automatically detect fiducials, correct image perspective, overlay component design data, and compare board images to detect manufacturing defects.

## Features

- **Automatic Fiducial Detection**: Locates fiducial markers using template matching to accurately register PCB images.
- **Perspective Transformation**: Warps camera images to a flat, orthogonal top-down view based on detected fiducials.
- **Component Overlay**: Visualizes component designators and package outlines based on `.mnt` pick-and-place files.
- **Defect Detection**: Compares a "Reference" image against a "Target" image to identify missing, skewed, or incorrect components.
- **Package Configuration**: Dedicated GUI to manage physical dimensions of various component packages for accurate rendering.
- **Interactive Viewer**: Zoomable inspection window with toggleable overlays, grids, comparison results, and a real-time status bar showing cursor coordinates in board millimeters.

## Installation

### Prerequisites

The core inspection tools are written in Python. Ensure you have **Python 3.x** installed along with the following libraries:

- `numpy`
- `opencv-python`
- `pillow` (PIL)
- `tkinter` (usually included with standard Python installations)

You can install the required packages via pip:

```bash
pip install numpy opencv-python pillow
```

### Web Development (Optional)

If working with the web interface components (`gulpfile.js`), you will need:
- Node.js and npm
- Gulp CLI

## Usage

### 1. Package Configuration

Before processing images, it is recommended to define the dimensions of the component packages used on your PCB. This ensures accurate bounding boxes for visual overlays and automated comparison.

```bash
python python/packages_config.py
```

This opens a GUI where you can view existing package data and double-click the Width/Length columns to edit dimensions (in millimeters). Data is saved to `packages_config.json`.

### 2. PCB Processing & Inspection

The main script `pcb_processing.py` handles image analysis. It expects companion files (`.mnt` and `.cfg`) to exist in the same directory as the input image with the same filename prefix.

**Syntax:**
```bash
python python/pcb_processing.py <path_to_image> [path_to_second_image]
```

#### Single Image Mode
Analyzes a single PCB image, finds fiducials, and displays the corrected image with component overlays.

```bash
python python/pcb_processing.py data/board_v1.jpg
```

#### Comparison Mode
To check for defects, provide a second image. The first image acts as the reference (Golden Sample), and the second is the target to be inspected.

```bash
python python/pcb_processing.py data/reference.jpg data/test_board.jpg
```

The tool will align both images and perform a component-by-component template match, highlighting mismatches in the results window.

## File Formats

### Component Placement (`.mnt`)
A text file defining the position of components.
**Format:** `Designator X Y Rotation Value Package`

```text
C1 10.5 20.0 90 100nF 0402
U1 30.0 40.0 0  MCU   TQFP32
```

### Board Configuration (`.cfg`)
A configuration file defining the physical dimensions of the PCB in millimeters.

```ini
pcb_width = 100.0
pcb_height = 80.0
```

*Note: The system requires a fiducial template image located at `python/templates/fiducial.tif` to function correctly.*