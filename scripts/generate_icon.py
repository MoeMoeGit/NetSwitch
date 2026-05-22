"""生成应用图标 - 深青色圆角方形 + 白色 N + 右下角横线"""

from PIL import Image, ImageDraw, ImageFont


def generate_icon(size=256):
    """生成指定尺寸的图标"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角半径按比例缩放
    radius = int(42 * size / 256)

    # 深青色圆角矩形背景
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=(0x0E, 0x74, 0x90, 255),
    )

    # 白色粗体 N
    font_size = int(160 * size / 256)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("Arial Bold", font_size)
        except OSError:
            font = ImageFont.truetype("arial.ttf", font_size)

    text = "N"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    # 略微上移，给右下角横线留空间
    x = (size - text_w) / 2 - bbox[0]
    y = (size - text_h) / 2 - bbox[1] - size * 0.02
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    # 右下角两条白色圆角横线
    line_h = max(int(6 * size / 256), 2)
    line_radius = line_h // 2
    gap = int(8 * size / 256)

    # 第一条：较长，opacity 0.45
    line1_w = int(60 * size / 256)
    line1_x = size - line1_w - int(20 * size / 256)
    line1_y = size - int(30 * size / 256)
    draw.rounded_rectangle(
        [(line1_x, line1_y), (line1_x + line1_w, line1_y + line_h)],
        radius=line_radius,
        fill=(255, 255, 255, int(255 * 0.45)),
    )

    # 第二条：较短，opacity 0.25
    line2_w = int(40 * size / 256)
    line2_x = size - line2_w - int(20 * size / 256)
    line2_y = line1_y + line_h + gap
    draw.rounded_rectangle(
        [(line2_x, line2_y), (line2_x + line2_w, line2_y + line_h)],
        radius=line_radius,
        fill=(255, 255, 255, int(255 * 0.25)),
    )

    return img


def main():
    import os

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

    # 生成各尺寸
    sizes = [16, 32, 48, 256]
    images = {}
    for s in sizes:
        img = generate_icon(s)
        images[s] = img
        png_path = os.path.join(output_dir, f"icon_{s}.png")
        img.save(png_path)
        print(f"Generated: icon_{s}.png")

    # 打包成 icon.ico（包含全部四个尺寸）
    ico_path = os.path.join(output_dir, "icon.ico")
    images[256].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=[images[s] for s in sizes if s != 256],
    )
    print(f"Generated: icon.ico")

    # 托盘用 PNG
    for s in [16, 32]:
        tray_path = os.path.join(output_dir, f"tray_{s}.png")
        images[s].save(tray_path)
        print(f"Generated: tray_{s}.png")

    # 清理中间 PNG（保留 tray 用的和 ico）
    for s in sizes:
        png_path = os.path.join(output_dir, f"icon_{s}.png")
        if os.path.exists(png_path):
            os.remove(png_path)

    print("\nDone! Generated files:")
    print(f"  - icon.ico (multi-size)")
    print(f"  - tray_16.png (tray)")
    print(f"  - tray_32.png (tray)")


if __name__ == "__main__":
    main()
