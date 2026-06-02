import fitz
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# A4 横版，300 DPI
A4_W = 3508
A4_H = 2480


def render_pdf_page(pdf_path, page_index=0, zoom=4):
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def detect_blue_boxes(img):
    """
    检测主标、地址标 PDF 里的蓝色/青色标签框。
    只保留竖向长方形标签。
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # PDF 里的标签框偏青蓝色
    lower = np.array([85, 40, 40])
    upper = np.array([115, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        ratio = h / max(w, 1)

        if 30000 < area < 600000 and ratio > 2.0:
            boxes.append((x, y, w, h))

    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))

    # 去重
    unique = []
    for box in boxes:
        x, y, w, h = box
        duplicated = False
        for ux, uy, uw, uh in unique:
            if abs(x - ux) < 20 and abs(y - uy) < 20:
                duplicated = True
                break
        if not duplicated:
            unique.append(box)

    return unique


def detect_black_boxes(img):
    """
    检测洗水标第二页里的黑色大矩形标签框。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)[1]

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        ratio = h / max(w, 1)

        if 30000 < area < 350000 and ratio > 2.0:
            boxes.append((x, y, w, h))

    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))

    # 去重
    unique = []
    for box in boxes:
        x, y, w, h = box
        duplicated = False
        for ux, uy, uw, uh in unique:
            if abs(x - ux) < 20 and abs(y - uy) < 20:
                duplicated = True
                break
        if not duplicated:
            unique.append(box)

    return unique


def crop_from_box(img, box, pad=3):
    x, y, w, h = box
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img.shape[1], x + w + pad)
    y2 = min(img.shape[0], y + h + pad)
    return img[y1:y2, x1:x2]


def extract_main_label(main_pdf):
    img = render_pdf_page(main_pdf, 0, zoom=4)
    boxes = detect_blue_boxes(img)

    if not boxes:
        return img

    # 主标取第一个蓝框标签
    return crop_from_box(img, boxes[0], pad=4)


def extract_address_parts(addr_pdf):
    img = render_pdf_page(addr_pdf, 0, zoom=4)
    boxes = detect_blue_boxes(img)

    parts = []
    for box in boxes[:3]:
        parts.append(crop_from_box(img, box, pad=4))

    # SIDE 02 在原 PDF 里是倒置的，旋转成正常方向
    if len(parts) >= 2:
        parts[1] = cv2.rotate(parts[1], cv2.ROTATE_180)

    return parts


def extract_wash_labels(wash_pdf):
    """
    只处理第三个 PDF 的第 2 页。
    提取黑色矩形水洗标，并剔除空白标。
    """
    img = render_pdf_page(wash_pdf, 1, zoom=4)
    boxes = detect_black_boxes(img)

    labels = []
    for box in boxes:
        crop = crop_from_box(img, box, pad=3)
        h, w = crop.shape[:2]

        # 判断是否空白：只统计内部文字，不把边框算进去
        mx = max(8, int(w * 0.08))
        my = max(8, int(h * 0.08))
        inner = crop[my:h - my, mx:w - mx]

        gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
        ink = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)[1]
        ink_pixels = cv2.countNonZero(ink)

        # front3 这种只有少量文字的也要保留，所以阈值不能太高
        if ink_pixels > 400:
            labels.append(crop)

    return labels


def get_font(size=36):
    possible_fonts = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    for path in possible_fonts:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    return ImageFont.load_default()


def paste_fit(canvas, arr, x, y, max_w, max_h, draw_border=True):
    """
    等比例缩放粘贴。
    为了接近目标图，外面统一画绿色标签框。
    """
    img = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))
    img.thumbnail((max_w, max_h), Image.LANCZOS)

    x = int(x)
    y = int(y)
    canvas.paste(img, (x, y))

    if draw_border:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [x, y, x + img.width, y + img.height],
            outline=(0, 170, 85),
            width=3
        )

    return img.width, img.height


def draw_text(draw, text, x, y, size=36, color=(0, 0, 0)):
    font = get_font(size)
    draw.text((x, y), text, fill=color, font=font)


def generate_final_pdf(main_pdf, addr_pdf, wash_pdf, output_pdf, preview_png=None):
    """
    目标格式：和用户提供的最终效果图一致。
    横版 A4：
    - 左侧：主标
    - 中间：地址标正面、地址标背面、Logo
    - 右侧：有效洗水标，两行多列排布
    """
    main_label = extract_main_label(main_pdf)
    addr_parts = extract_address_parts(addr_pdf)
    wash_labels = extract_wash_labels(wash_pdf)

    canvas = Image.new("RGB", (A4_W, A4_H), "white")
    draw = ImageDraw.Draw(canvas)

    # 标题区域
    draw_text(draw, "2026. 5. 2", 75, 75, size=42, color=(255, 0, 0))
    draw_text(draw, "规格:2x12cm(含车位上下各0.5cm)", 70, 130, size=20)
    draw_text(draw, "Order No  2052740/75", 1480, 45, size=56)

    # 标签规格文字
    draw_text(draw, "规格:2x6cm(含车位0.5cm)", 575, 75, size=28)
    draw_text(draw, "正面", 575, 125, size=24)
    draw_text(draw, "背面", 1060, 125, size=24)
    draw_text(draw, "正面", 1545, 125, size=24)

    draw_text(draw, "规格:2x6cm(含车位0.5cm)", 2050, 75, size=28)

    # 左侧主标
    paste_fit(canvas, main_label, 70, 180, 360, 2180)

    # 地址标：正面、背面、Logo
    addr_positions = [
        (565, 180),
        (1060, 180),
        (1545, 180),
    ]

    for i, part in enumerate(addr_parts[:3]):
        paste_fit(canvas, part, addr_positions[i][0], addr_positions[i][1], 360, 1080)

    # 洗水标区域：按照目标效果图的横版两行多列排版
    # 这里直接按页面顺序排，空白已过滤
    wash_positions = [
        (2050, 180),   # 正面1
        (2545, 180),   # 背面1
        (565, 1365),   # 正面2
        (1060, 1365),  # 背面2
        (1545, 1365),  # 正面3
        (2050, 1365),  # 正面4
        (2545, 1365),  # 背面4
        (3040, 1365),  # 正面5 / 额外有效标
    ]

    for i, label in enumerate(wash_labels):
        if i >= len(wash_positions):
            break

        x, y = wash_positions[i]
        paste_fit(canvas, label, x, y, 360, 1080)

    # 保存 PDF
    canvas.save(output_pdf, "PDF", resolution=300.0)

    # 保存网页预览 PNG
    if preview_png:
        preview = canvas.copy()
        preview.thumbnail((1600, 1131), Image.LANCZOS)
        preview.save(preview_png)

    return output_pdf
