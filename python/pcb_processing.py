#!/usr/bin/python
import sys
import numpy as np
import cv2
import ntpath

fiducialTemplate = './python/templates/fiducial.tif'

fiducialPositions = list()
destPos = np.float32([[0,0],[800,0],[800,800],[0,800]])

# Reference: https://www.pyimagesearch.com/2014/08/25/4-point-opencv-getperspective-transform-example/
def four_point_transform(image, pts):
	# obtain a consistent order of the points and unpack them
	# individually
	rect = np.asarray(pts, np.float32) # order_points(pts)
	(tl, tr, br, bl) = rect

	# compute the width of the new image, which will be the
	# maximum distance between bottom-right and bottom-left
	# x-coordiates or the top-right and top-left x-coordinates
	widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
	widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
	maxWidth = max(int(widthA), int(widthB))

	# compute the height of the new image, which will be the
	# maximum distance between the top-right and bottom-right
	# y-coordinates or the top-left and bottom-left y-coordinates
	heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
	heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
	maxHeight = max(int(heightA), int(heightB))

	# now that we have the dimensions of the new image, construct
	# the set of destination points to obtain a "birds eye view",
	# (i.e. top-down view) of the image, again specifying points
	# in the top-left, top-right, bottom-right, and bottom-left
	# order
	dst = np.array([
		[0, 0],
		[maxWidth - 1, 0],
		[maxWidth - 1, maxHeight - 1],
		[0, maxHeight - 1]], dtype = "float32")

	# compute the perspective transform matrix and then apply it
	M = cv2.getPerspectiveTransform(rect, dst)
	warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

	# return the warped image
	return warped

def findFiducial(imgGray, fiducial, region):
    x, y, w, h = region
    #imageWidth, imageHeight = imgGray.shape[:2]
    print('ROI width: ' + str(w) + " height: " + str(h))

    roi = imgGray[y:y + h, x:x + w]
    res = cv2.matchTemplate(roi, fiducial, cv2.TM_CCOEFF_NORMED)
    threshold = 0.9

    templateWidth, templateHeight =  fiducial.shape[::-1]
    
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    print('Max loc: ' + str(max_loc))

    fiducialPos = [(x + max_loc[0], y + max_loc[1]), (x + max_loc[0] + templateWidth, y + max_loc[1] + templateHeight)]
    #cv2.rectangle(imgRef, fiducialPos[0], fiducialPos[1], (0,255,255), 3, cv2.LINE_AA)
    #cv2.rectangle(imgGray, fiducialPos[0], fiducialPos[1], (0,0,0), -1)

    fiducialCenterPos = (fiducialPos[0][0] + int(templateWidth / 2),fiducialPos[0][1] + int(templateHeight / 2))
    #cv2.drawMarker(imgRef, fiducialCenterPos, (0,0,255), cv2.MARKER_TILTED_CROSS, 100, 3, cv2.LINE_AA)
    
    fiducialPositions.append(fiducialCenterPos)

# sys.argv[1] -> image path
def main():
    print("apertus° PCB inspection / version 0.1a")
    if len(sys.argv) < 2:
        print("No image path defined, example: python pcb_processing.py <path>")
        exit

    imageToProcess = sys.argv[1]

    # Load images, convert to grayscale for template matching
    imgRef = cv2.imread(imageToProcess, 1)
    imgGray = cv2.cvtColor(imgRef, cv2.COLOR_RGB2GRAY)
    fiducial = cv2.imread(fiducialTemplate, 0)

    imageHeight, imageWidth = imgGray.shape[:2]
    print('Image width: ' + str(imageWidth) + " height: " + str(imageHeight))

    findFiducial(imgGray, fiducial, (0, 0, int(imageWidth / 2), int(imageHeight / 2)))
    findFiducial(imgGray, fiducial, (int(imageWidth / 2), 0, int(imageWidth / 2), int(imageHeight / 2)))
    findFiducial(imgGray, fiducial, (int(imageWidth / 2), int(imageHeight / 2), int(imageWidth / 2), int(imageHeight / 2)))
    findFiducial(imgGray, fiducial, (0, int(imageHeight / 2), int(imageWidth / 2), int(imageHeight / 2)))

    for pt in np.asarray(fiducialPositions):
        print("P1: " + str(pt[0]) + " P2: "+ str(pt[1]))

    imgAdj = four_point_transform(imgRef, fiducialPositions) 

    fileName = ntpath.basename(sys.argv[1])
    #outputFileName = './tmp/' + fileName + '_warp.png'
    outputFileName = './tmp/warp.png'
    print('Output: ' + outputFileName)
    cv2.imwrite(outputFileName, imgAdj)

    return outputFileName

main()