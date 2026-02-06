#!/usr/bin/env python3
"""Remove white background from an image and make it transparent."""
from PIL import Image

def remove_white_background(input_path, output_path, threshold=240):
    img = Image.open(input_path)
    img = img.convert("RGBA")
    datas = img.getdata()
    new_data = []
    for item in datas:
        if item[0] >= threshold and item[1] >= threshold and item[2] >= threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    img.save(output_path, "PNG")
    print(f"✓ Saved transparent image to: {output_path}")

if __name__ == "__main__":
    remove_white_background("founder.jpg", "founder_transparent.png", threshold=240)
