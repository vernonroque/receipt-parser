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
    # webCamFeed = True
    # cap = cv2.VideoCapture(1)
    # cap.set(10, 160)
    heightImg = 640
    widthImg = 480
    #initialize_trackbars()

    #Youtube example has a initialize trackbars() function
    count = 0
    while True:

        # Decode image bytes to OpenCV format
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return image_bytes
        orig = image.copy()
        print(f"Original image size: {len(image_bytes):,} bytes")
        print ("the data type of the image is ", type(image))

        #BLANK IMAGE
        imgBlank = np.zeros((heightImg, widthImg, 3), np.uint8)  # CREATE A BLANK IMAGE FOR TESTING

        # if webCamFeed: success, img = cap.read()

        img = cv2.resize(orig, (widthImg, heightImg))  # RESIZE IMAGE
    
        # Step 1: Grayscale
        imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # CONVERT IMAGE TO GRAY SCALE

        # Step 2: Edge detection
        imgBlur = cv2.GaussianBlur(imgGray, (5, 5), 1)  # ADD GAUSSIAN BLUR
        #thres = val_trackbars()  # GET TRACK BAR VALUES FOR THRESHOLDS
        imgThreshold = cv2.Canny(imgBlur, 75, 200)  # APPLY CANNY BLUR

        kernel = np.ones((5, 5))
        imgDial = cv2.dilate(imgThreshold, kernel, iterations=4)  # APPLY DILATION
        imgThreshold = cv2.erode(imgDial, kernel, iterations=1)  # APPLY EROSION

        # Step 3: Find contours
        ## FIND ALL CONTOURS
        imgContours = img.copy()  # COPY IMAGE FOR DISPLAY PURPOSES
        imgBigContour = img.copy()  # COPY IMAGE FOR DISPLAY PURPOSES
        contours, hierarchy = cv2.findContours(imgThreshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(imgContours, contours, -1, (0, 255, 0), 10)  # DRAW ALL DETECTED CONTOURS

        # Step 4: Biggest contour that is a quadrilateral
        # FIND THE BIGGEST CONTOUR
        biggest, maxArea = biggestContour(contours)  # FIND THE BIGGEST CONTOUR
        if biggest.size != 0:
            biggest = reorder(biggest)
            cv2.drawContours(imgBigContour, biggest, -1, (0, 255, 0), 20)  # DRAW THE BIGGEST CONTOUR
            imgBigContour = drawRectangle(imgBigContour, biggest, 2)
            pts1 = np.float32(biggest)  # PREPARE POINTS FOR WARP
            pts2 = np.float32([[0, 0], [widthImg, 0], [0, heightImg], [widthImg, heightImg]])  # PREPARE POINTS FOR WARP
            matrix = cv2.getPerspectiveTransform(pts1, pts2)
            imgWarpColored = cv2.warpPerspective(img, matrix, (widthImg, heightImg))

            #REMOVE 20 PIXELS FROM EACH SIDE
            imgWarpColored = imgWarpColored[20:imgWarpColored.shape[0] - 20, 20:imgWarpColored.shape[1] - 20]
            imgWarpColored = cv2.resize(imgWarpColored, (widthImg, heightImg))

            # APPLY ADAPTIVE THRESHOLD
            imgWarpGray = cv2.cvtColor(imgWarpColored, cv2.COLOR_BGR2GRAY)
            imgAdaptiveThre = cv2.adaptiveThreshold(imgWarpGray, 255, 1, 1, 7, 2)
            imgAdaptiveThre = cv2.bitwise_not(imgAdaptiveThre)
            imgAdaptiveThre = cv2.medianBlur(imgAdaptiveThre, 3)

        _, encoded = cv2.imencode('.jpg', imgAdaptiveThre)
        return encoded.tobytes()


    # Step 5: Warp perspective on original color image
    warped = apply_warp(orig, doc_cnt)
    cv2.imwrite("tmp/debug_warped.jpg", warped)  # DEBUG: remove after diagnosis

    # Step 6: Adaptive thresholding → scanned paper effect
    warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    scanned = cv2.adaptiveThreshold(
        warped_gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=10,
    )

    _, encoded = cv2.imencode('.jpg', scanned, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()
