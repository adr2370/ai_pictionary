"""Generate a seamless paper texture for the Pictionary video background."""
import os
import random
from PIL import Image, ImageDraw, ImageFilter

def generate_paper_texture(width=1080, height=1920, output_path="assets/paper_texture.png"):
    """Generate a warm, subtly textured paper background that tiles vertically."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Base color: warm off-white (sketchbook paper)
    base_r, base_g, base_b = 245, 240, 230

    img = Image.new('RGB', (width, height), (base_r, base_g, base_b))
    pixels = img.load()

    # Add subtle noise/grain
    random.seed(42)  # Reproducible texture
    for y in range(height):
        for x in range(width):
            noise = random.randint(-8, 8)
            r = max(0, min(255, base_r + noise))
            g = max(0, min(255, base_g + noise))
            b = max(0, min(255, base_b + noise - 2))
            pixels[x, y] = (r, g, b)

    # Add very subtle horizontal fiber lines
    draw = ImageDraw.Draw(img)
    for _ in range(40):
        y_pos = random.randint(0, height - 1)
        opacity_variation = random.randint(-3, 3)
        line_color = (base_r + opacity_variation - 10,
                      base_g + opacity_variation - 10,
                      base_b + opacity_variation - 12)
        draw.line([(0, y_pos), (width, y_pos)], fill=line_color, width=1)

    # Slight blur to soften the grain
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Make vertically seamless: blend top and bottom 100px
    blend_height = 100
    for y in range(blend_height):
        alpha = y / blend_height
        for x in range(width):
            top_pixel = img.getpixel((x, y))
            bottom_pixel = img.getpixel((x, height - blend_height + y))
            blended = tuple(int(bottom_pixel[c] * (1 - alpha) + top_pixel[c] * alpha) for c in range(3))
            img.putpixel((x, y), blended)
            img.putpixel((x, height - blend_height + y), blended)

    img.save(output_path, 'PNG')
    print(f"Paper texture saved to {output_path} ({width}x{height})")

if __name__ == "__main__":
    generate_paper_texture()
