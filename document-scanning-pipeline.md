# Document Scanning Pipeline (CamScanner-style)

## Step 1: Image Capture
- Capture a frame from the camera (or accept an uploaded image)
- Ensure sufficient resolution (ideally 1080p+)
- Apply basic exposure/brightness normalization before processing

---

## Step 2: Edge Detection & Preprocessing
Convert the image to a format suitable for contour detection:

1. **Grayscale conversion** — reduces complexity
2. **Gaussian blur** — removes noise that causes false edges
3. **Canny edge detection** — finds sharp transitions (document borders)
4. **Dilation/morphological closing** — connects broken edge lines

---

## Step 3: Document Contour Detection
Find the document's four corners:

1. Use `findContours()` (OpenCV) on the edge map
2. Filter contours by **area** (ignore small noise)
3. Use `approxPolyDP()` to approximate contours to polygons
4. Select the **largest 4-sided polygon** — that's your document

---

## Step 4: Perspective Transform (The Core "Flatten" Step)
This is what makes the document look flat and upright:

1. **Order the 4 corners** consistently: top-left, top-right, bottom-right, bottom-left
2. **Calculate output dimensions** — use the longest detected width/height
3. **Compute the homography matrix** with `getPerspectiveTransform()`
4. **Apply `warpPerspective()`** to produce a bird's-eye, flat document image

---

## Step 5: Post-Processing (Enhancement)
Make it look clean and readable:

| Mode | Technique |
|---|---|
| **Magic Color** | Adaptive thresholding + color boost |
| **Grayscale** | Convert + contrast stretch |
| **Black & White** | Otsu's binarization |
| **Photo** | Mild sharpening only |

Key operations:
- **Adaptive thresholding** (`cv2.adaptiveThreshold`) — handles uneven lighting
- **Sharpening kernel** — makes text crisp
- **White balance correction** — removes paper color cast

---

## Step 6: Auto-Rotation / Orientation Correction
Ensure the document is upright:

1. Run **Hough Line Transform** to detect dominant text/line angles
2. Calculate the skew angle
3. Rotate the warped image to correct it
4. Alternatively, use an **ML model** (e.g., a lightweight CNN) to classify orientation (0°, 90°, 180°, 270°)

---

## Step 7: Output
- Export as **PDF** (embed as image inside PDF) or **JPEG/PNG**
- Optionally run **OCR** (Tesseract / Google ML Kit) to make it searchable

---

## Recommended Stack

| Layer | Tool |
|---|---|
| Core CV | OpenCV (Python or C++) |
| Mobile | OpenCV Android/iOS SDK or CameraX |
| ML fallback | TensorFlow Lite / PyTorch Mobile |
| OCR | Tesseract or Google ML Kit |

---

## Key Insight
The "magic" is really **Step 4 (perspective warp)**. Everything else is polish. Start by nailing `getPerspectiveTransform` + `warpPerspective` with manually selected corners, then layer on automatic corner detection and enhancement afterward.