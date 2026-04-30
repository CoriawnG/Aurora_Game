from PIL import Image, ImageDraw
import os

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

# helper to generate a pixel portrait by painting a small grid and upscaling
def make_portrait(filename, palette, pattern_seed=0):
    w, h = 16, 16
    img = Image.new('RGB', (w, h), palette[0])
    draw = ImageDraw.Draw(img)
    import random
    r = random.Random(pattern_seed)
    for y in range(h):
        for x in range(w):
            # background noise
            if r.random() < 0.12:
                color = palette[1]
            else:
                color = palette[0]
            # face area
            if 3 < x < 12 and 2 < y < 13:
                if r.random() < 0.9:
                    color = palette[2]
            # eyes
            if (x in (6,9)) and y == 7:
                color = (0,0,0)
            # mouth
            if x in range(6,10) and y == 10 and r.random() < 0.6:
                color = palette[3]
            draw.point((x,y), fill=color)
    # upscale with nearest neighbor to preserve pixels
    big = img.resize((128,128), Image.NEAREST)
    out_path = os.path.join(IMAGES_DIR, filename)
    big.save(out_path)
    print('Saved', out_path)

# create three portraits with different palettes
make_portrait('advisor_economy.png', [(200,180,120),(180,160,90),(240,210,140),(120,80,40)], pattern_seed=1)
make_portrait('advisor_rights.png', [(150,200,200),(120,170,170),(200,240,240),(50,120,120)], pattern_seed=2)
make_portrait('advisor_security.png', [(200,150,180),(170,120,140),(240,180,210),(120,60,80)], pattern_seed=3)

# generate a simple tiled background
bg_small = Image.new('RGB', (48,32), (20,18,30))
d = ImageDraw.Draw(bg_small)
for y in range(0,32,8):
    for x in range(0,48,8):
        if (x+y) % 16 == 0:
            d.rectangle([x,y,x+7,y+7], fill=(30,25,40))
        else:
            d.rectangle([x,y,x+7,y+7], fill=(22,18,32))
big_bg = bg_small.resize((960,640), Image.NEAREST)
big_bg.save(os.path.join(IMAGES_DIR, 'background.png'))
print('Saved background')

# small UI icon for flag
flag = Image.new('RGB', (32,24), (80,40,40))
d = ImageDraw.Draw(flag)
d.rectangle([0,0,31,23], fill=(80,40,40))
d.rectangle([6,4,26,15], fill=(200,60,80))
flag.resize((96,72), Image.NEAREST).save(os.path.join(IMAGES_DIR,'aurora_flag.png'))
print('Saved flag')
