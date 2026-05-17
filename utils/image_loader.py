# utils/image_loader.py
import cv2, numpy as np
from PIL import Image

def load_template(path):
    tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if tpl is not None:
        return tpl
    try:
        return np.array(Image.open(path).convert('L'))
    except:
        return None