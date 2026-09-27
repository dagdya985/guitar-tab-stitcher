import cv2
import numpy as np


def prepare(image: np.ndarray, clahe: bool = True, binary: bool = False) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    if clahe:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if binary:
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 21, 8)
    return gray


def edge_image(gray: np.ndarray) -> np.ndarray:
    x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(x, y)

