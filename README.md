# Printed Circuit Board - Automated Optical Inspection

## Goals

This software is meant to help you indentify issues with populated printed circuit boards. You provide a reference image of the "good" PCB and then the software shall analyse additional boards and identify differences (wrong components, placement/orientation errors, solder bridges, etc.).

## Current Development state

First prototype for unwrapping the PCB based on fiducials done, no other functionality yet.

## Requirements

python packages: numpy, opencv-python


## Usage

```python3 python/pcb_processing.py test_images/SKL8517-2-REWORKED-TOP2.tif```
 