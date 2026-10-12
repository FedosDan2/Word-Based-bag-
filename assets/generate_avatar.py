from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT = Path(__file__).with_name("bugizslov-avatar.png")
JPG_OUT = Path(__file__).with_name("bugizslov-avatar.jpg")


def lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


image = Image.new("RGBA", (SIZE, SIZE))
pixels = image.load()
for y in range(SIZE):
    for x in range(SIZE):
        t = (x + y) / (2 * (SIZE - 1))
        pixels[x, y] = (lerp(30, 75, t), lerp(51, 71, t), lerp(119, 205, t), 255)

mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).ellipse((22, 22, SIZE - 22, SIZE - 22), fill=255)
image.putalpha(mask)
draw = ImageDraw.Draw(image)

# Speech bubble.
draw.rounded_rectangle((154, 158, 858, 760), radius=185, fill=(247, 250, 255, 255))
draw.polygon([(626, 690), (792, 690), (742, 842)], fill=(247, 250, 255, 255))

# Three dots suggest a conversation.
for x in (287, 384, 481):
    draw.rounded_rectangle((x - 35, 292, x + 35, 350), radius=29, fill=(97, 128, 211, 255))

# Antennae and six legs.
ink = (38, 45, 80, 255)
draw.line([(600, 373), (554, 318), (526, 316)], fill=ink, width=22, joint="curve")
draw.line([(692, 373), (742, 318), (770, 316)], fill=ink, width=22, joint="curve")
draw.ellipse((501, 291, 548, 338), fill=(255, 197, 77, 255))
draw.ellipse((748, 291, 795, 338), fill=(255, 197, 77, 255))
for y, dy in ((526, -50), (620, 0), (710, 52)):
    draw.line([(520, y), (432, y + dy)], fill=ink, width=24)
    draw.line([(733, y), (821, y + dy)], fill=ink, width=24)

# Friendly beetle, built from bold shapes that stay legible at small size.
draw.ellipse((545, 354, 710, 516), fill=ink)
draw.ellipse((496, 420, 760, 739), fill=(242, 89, 75, 255), outline=ink, width=23)
draw.pieslice((507, 431, 747, 722), start=180, end=360, fill=(255, 125, 92, 255))
draw.line([(628, 455), (628, 718)], fill=ink, width=19)
draw.ellipse((574, 397, 607, 430), fill=(255, 255, 255, 255))
draw.ellipse((648, 397, 681, 430), fill=(255, 255, 255, 255))
draw.ellipse((585, 407, 599, 421), fill=ink)
draw.ellipse((659, 407, 673, 421), fill=ink)
draw.arc((605, 429, 651, 465), start=15, end=165, fill=(255, 255, 255, 255), width=8)

# A small warm spark adds energy without crowding the mark.
draw.ellipse((779, 517, 817, 555), fill=(255, 197, 77, 255))
draw.ellipse((807, 564, 829, 586), fill=(255, 255, 255, 255))

image = image.convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
image.save(OUT, format="PNG", optimize=True)
image.save(JPG_OUT, format="JPEG", quality=95, optimize=True)
