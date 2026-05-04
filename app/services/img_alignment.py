import cv2
import numpy as np
from app.services.img_enhancement import order_points, apply_warp

def initialize_trackbars(initial_trackbar_vals=0):
    cv2.namedWindow("Trackbars")
    cv2.resizeWindow("Trackbars", 360, 240)
    cv2.createTrackbar("Threshold1", "Trackbars", 200, 255, lambda x: None)
    cv2.createTrackbar("Threshold2", "Trackbars", 200, 255, lambda x: None)

def val_trackbars():
    Theshold1 = cv2.getTrackbarPos("Threshold1", "Trackbars")
    Theshold2 = cv2.getTrackbarPos("Threshold2", "Trackbars")
    src = Theshold1, Theshold2
    return src

def biggest_rect_from_contours(contours):
    if not contours:
        return np.array([])
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 5000:
        return np.array([])
    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    return np.int32(box).reshape(4, 1, 2)

def biggestContour(contours):
    biggest = np.array([])
    max_area = 0
    for i in contours:
        area = cv2.contourArea(i)
        if area > 5000:
            peri = cv2.arcLength(i, True)
            approx = cv2.approxPolyDP(i, 0.02 * peri, True)
            if area > max_area and len(approx) == 4:
                biggest = approx
                max_area = area
    return biggest, max_area

def reorder(myPoints):
    myPoints = myPoints.reshape((4, 2))
    myPointsNew = np.zeros((4, 1, 2), dtype=np.int32)
    add = myPoints.sum(1)

    myPointsNew[0] = myPoints[np.argmin(add)]
    myPointsNew[3] = myPoints[np.argmax(add)]
    diff = np.diff(myPoints, axis=1)
    myPointsNew[1] = myPoints[np.argmin(diff)]
    myPointsNew[2] = myPoints[np.argmax(diff)]

    return myPointsNew

def drawRectangle(img, biggest, thickness):
    cv2.line(img, (biggest[0][0][0], biggest[0][0][1]), (biggest[1][0][0], biggest[1][0][1]), (0, 255, 0), thickness)
    cv2.line(img, (biggest[1][0][0], biggest[1][0][1]), (biggest[2][0][0], biggest[2][0][1]), (0, 255, 0), thickness)
    cv2.line(img, (biggest[2][0][0], biggest[2][0][1]), (biggest[3][0][0], biggest[3][0][1]), (0, 255, 0), thickness)
    cv2.line(img, (biggest[3][0][0], biggest[3][0][1]), (biggest[0][0][0], biggest[0][0][1]), (0, 255, 0), thickness)
    return img

def align_images(image_bytes: bytes) -> bytes:
    heightImg = 640
    widthImg = 480

    # Decode image bytes to OpenCV format
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        return image_bytes
    orig = image.copy()
    print(f"Original image size: {len(image_bytes):,} bytes")
    print("the data type of the image is ", type(image))

    img = cv2.resize(orig, (widthImg, heightImg))

    # Step 1: Grayscale
    imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2: Edge detection
    imgBlur = cv2.GaussianBlur(imgGray, (5, 5), 1)
    imgThreshold = cv2.Canny(imgBlur, 75, 200)

    kernel = np.ones((5, 5))
    imgDial = cv2.dilate(imgThreshold, kernel, iterations=4)
    imgThreshold = cv2.erode(imgDial, kernel, iterations=1)

    # Step 3: Find contours
    imgContours = img.copy()
    imgBigContour = img.copy()
    contours, hierarchy = cv2.findContours(imgThreshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(imgContours, contours, -1, (0, 255, 0), 10)

    # Step 4: Find biggest clean 4-point contour; fall back to minAreaRect
    biggest, maxArea = biggestContour(contours)
    if biggest.size == 0:
        print("No contour with 4 points found, trying minAreaRect...")
        #biggest = biggest_rect_from_contours(contours)

    if biggest.size != 0:
        biggest = reorder(biggest)
        cv2.drawContours(imgBigContour, biggest, -1, (0, 255, 0), 20)
        imgBigContour = drawRectangle(imgBigContour, biggest, 2)
        pts1 = np.float32(biggest)
        pts2 = np.float32([[0, 0], [widthImg, 0], [0, heightImg], [widthImg, heightImg]])
        matrix = cv2.getPerspectiveTransform(pts1, pts2)
        imgWarpColored = cv2.warpPerspective(img, matrix, (widthImg, heightImg))

        imgWarpColored = imgWarpColored[20:imgWarpColored.shape[0] - 20, 20:imgWarpColored.shape[1] - 20]
        imgWarpColored = cv2.resize(imgWarpColored, (widthImg, heightImg))

        imgWarpGray = cv2.cvtColor(imgWarpColored, cv2.COLOR_BGR2GRAY)
        # imgAdaptiveThre = cv2.adaptiveThreshold(imgWarpGray, 255, 1, 1, 7, 2)
        # imgAdaptiveThre = cv2.bitwise_not(imgAdaptiveThre)
        # imgAdaptiveThre = cv2.medianBlur(imgAdaptiveThre, 3)

        _, encoded = cv2.imencode('.jpg', imgWarpGray)
        return encoded.tobytes()

    # Nothing detected — return resized original
    _, encoded = cv2.imencode('.jpg', image)
    return encoded.tobytes()
