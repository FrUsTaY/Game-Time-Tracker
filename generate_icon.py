"""
generate_icon.py — скрипт для генерации иконки GameTimeTracker.
Создаёт иконку в неоновом стиле (таймер/песочные часы) и сохраняет в assets/.
Запускать один раз перед сборкой или при отсутствии иконок.

Расположение: GameTimeTracker/generate_icon.py
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def generate_icon_png(size: int = 256) -> Image.Image:
    """
    Генерирует квадратную иконку с неоновым таймером.
    
    Args:
        size: размер иконки в пикселях (ширина = высота)
    
    Returns:
        PIL Image объект с иконкой
    """
    # Цвета
    bg_dark = (13, 13, 13)        # #0d0d0d
    neon_cyan = (0, 212, 255)     # #00d4ff
    neon_purple = (123, 47, 255)  # #7b2fff
    neon_pink = (255, 51, 204)    # #ff33cc (дополнительный акцент)
    
    # Создаём изображение с альфа-каналом
    img = Image.new('RGBA', (size, size), bg_dark + (255,))
    draw = ImageDraw.Draw(img)
    
    # Центр и базовые параметры
    cx, cy = size // 2, size // 2
    outer_radius = int(size * 0.4)
    inner_radius = int(size * 0.25)
    
    # --- 1. Рисуем круглую рамку (неоновое кольцо) ---
    # Внешнее свечение (размытое)
    ring_outer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw_ring = ImageDraw.Draw(ring_outer)
    draw_ring.ellipse(
        (cx - outer_radius, cy - outer_radius, cx + outer_radius, cy + outer_radius),
        outline=neon_cyan,
        width=int(size * 0.04)
    )
    # Применяем размытие для свечения
    ring_outer = ring_outer.filter(ImageFilter.GaussianBlur(radius=size * 0.02))
    img.paste(ring_outer, (0, 0), ring_outer)
    
    # Основное кольцо (чёткое)
    draw.ellipse(
        (cx - outer_radius, cy - outer_radius, cx + outer_radius, cy + outer_radius),
        outline=neon_cyan,
        width=int(size * 0.02)
    )
    
    # --- 2. Рисуем внутренний круг (таймер/песочные часы) ---
    # Фон внутреннего круга с градиентом (просто тёмный)
    draw.ellipse(
        (cx - inner_radius, cy - inner_radius, cx + inner_radius, cy + inner_radius),
        fill=(26, 26, 46, 255),  # #1a1a2e
        outline=neon_purple,
        width=int(size * 0.02)
    )
    
    # --- 3. Рисуем песочные часы или стрелки таймера ---
    # Верхняя и нижняя дуги (стилизованный песочные часы)
    draw.polygon([
        (cx, cy - inner_radius // 2),
        (cx - inner_radius // 2, cy),
        (cx, cy + inner_radius // 2),
        (cx + inner_radius // 2, cy)
    ], outline=neon_cyan, width=int(size * 0.02), fill=(0, 0, 0, 0))
    
    # Рисуем стрелки таймера (минутная и часовая)
    # Часовая стрелка (короткая)
    hour_end = (cx + int(inner_radius * 0.3), cy - int(inner_radius * 0.5))
    draw.line([(cx, cy), hour_end], fill=neon_purple, width=int(size * 0.025))
    # Минутная стрелка (длинная)
    minute_end = (cx + int(inner_radius * 0.6), cy - int(inner_radius * 0.3))
    draw.line([(cx, cy), minute_end], fill=neon_cyan, width=int(size * 0.015))
    
    # Центральная точка
    draw.ellipse(
        (cx - size//30, cy - size//30, cx + size//30, cy + size//30),
        fill=neon_pink
    )
    
    # --- 4. Добавляем текст "GT" внизу ---
    try:
        font_size = int(size * 0.12)
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
    
    text = "GT"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = cx - text_width // 2
    text_y = cy + int(inner_radius * 0.6)
    draw.text((text_x, text_y), text, fill=neon_cyan, font=font)
    
    # --- 5. Добавляем геймерские акценты (неоновые точки по краям) ---
    dot_radius = int(size * 0.03)
    for angle_deg in [45, 135, 225, 315]:
        rad = math.radians(angle_deg)
        x = cx + int(outer_radius * 1.05 * math.cos(rad))
        y = cy + int(outer_radius * 1.05 * math.sin(rad))
        draw.ellipse(
            (x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius),
            fill=neon_purple
        )
    
    return img


def save_icons():
    """Генерирует и сохраняет PNG и ICO файлы в папку assets."""
    os.makedirs("assets", exist_ok=True)
    
    img = generate_icon_png(256)
    
    png_path = "assets/icon.png"
    img.save(png_path, "PNG")
    print(f"Сохранён PNG: {png_path}")
    
    ico_path = "assets/icon.ico"
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for s in sizes:
        if s == 256:
            img_resized = img
        else:
            img_resized = img.resize((s, s), Image.Resampling.LANCZOS)
        images.append(img_resized)
    
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"Сохранён ICO: {ico_path}")


if __name__ == "__main__":
    save_icons()