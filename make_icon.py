"""BookMaker.ico を生成する。

PIL（Pillow）で青系の本アイコンを作成し、複数サイズを含む .ico に保存。
青角丸スクエア + 中央に「BM」イニシャル + 下部に「BookMaker」ラベル。

実行：
    python make_icon.py

出力：
    BookMaker.ico
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
ICO_PATH = BASE / "BookMaker.ico"
PNG_PREVIEW = BASE / "BookMaker.png"

# カラーパレット（プライマリーカラー #1E5BFF と統一）
PRIMARY = (30, 91, 255, 255)
PRIMARY_DARK = (24, 64, 184, 255)
ACCENT = (255, 255, 255, 255)
SHADOW = (12, 35, 90, 90)


def find_font_bold(sizes_to_try: list[int]) -> dict[int, ImageFont.FreeTypeFont]:
    """Windows / Mac / Linux で利用可能な太字フォントを探す。"""
    candidates = [
        "arialbd.ttf",                                       # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",                     # Segoe UI Bold
        "/Library/Fonts/Arial Bold.ttf",                     # Mac
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    ]
    fonts: dict[int, ImageFont.FreeTypeFont] = {}
    for size in sizes_to_try:
        for c in candidates:
            try:
                fonts[size] = ImageFont.truetype(c, size)
                break
            except (OSError, IOError):
                continue
        if size not in fonts:
            fonts[size] = ImageFont.load_default()
    return fonts


def render_canvas(canvas_size: int) -> Image.Image:
    """1サイズ分のアイコンを描画する。"""
    s = canvas_size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 影（背面）
    margin = max(int(s * 0.10), 1)
    radius = max(int(s * 0.18), 2)
    shadow_offset = max(int(s * 0.03), 1)
    if s >= 32:
        sh = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [(margin + shadow_offset, margin + shadow_offset),
             (s - margin + shadow_offset, s - margin + shadow_offset)],
            radius=radius,
            fill=SHADOW,
        )
        sh = sh.filter(ImageFilter.GaussianBlur(radius=max(s // 64, 1)))
        img = Image.alpha_composite(img, sh)
        draw = ImageDraw.Draw(img)

    # メイン角丸スクエア
    draw.rounded_rectangle(
        [(margin, margin), (s - margin, s - margin)],
        radius=radius,
        fill=PRIMARY,
    )

    # 本の背表紙ライン（左端）
    spine_w = max(int(s * 0.04), 1)
    spine_x = margin + max(int(s * 0.06), 1)
    draw.rectangle(
        [(spine_x, margin + radius // 2),
         (spine_x + spine_w, s - margin - radius // 2)],
        fill=PRIMARY_DARK,
    )

    # 「BM」イニシャル中央
    if s >= 24:
        font_size = max(int(s * 0.42), 8)
        fonts = find_font_bold([font_size])
        font = fonts[font_size]
        text = "BM"
        # textbbox で文字サイズ計測
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (s - tw) // 2 - bbox[0]
        ty = (s - th) // 2 - bbox[1] - max(int(s * 0.04), 0)
        draw.text((tx, ty), text, font=font, fill=ACCENT)

    # 小サイズではラベルなし、大きい時だけ「Book Maker」副題
    if s >= 128:
        font_size_sub = max(int(s * 0.10), 8)
        fonts_sub = find_font_bold([font_size_sub])
        sub = fonts_sub[font_size_sub]
        sub_text = "Book Maker"
        sb = draw.textbbox((0, 0), sub_text, font=sub)
        sw = sb[2] - sb[0]
        sx = (s - sw) // 2 - sb[0]
        sy = s - margin - int(s * 0.16) - sb[1]
        draw.text((sx, sy), sub_text, font=sub, fill=ACCENT)

    return img


def build_ico() -> None:
    sizes = [16, 24, 32, 48, 64, 96, 128, 256]
    images = [render_canvas(s) for s in sizes]
    base = images[-1]
    base.save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    base.save(PNG_PREVIEW, format="PNG")
    print(f"[OK] {ICO_PATH} ({ICO_PATH.stat().st_size} B)")
    print(f"[OK] {PNG_PREVIEW} ({PNG_PREVIEW.stat().st_size} B) ← プレビュー用")


if __name__ == "__main__":
    build_ico()
