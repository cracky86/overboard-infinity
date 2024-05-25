import string
import random
import math
from PIL import Image, ImageDraw, ImageFont

# Generate random string for CAPTCHA
def generate_captcha_text(length=4):
    letters = string.digits
    return ''.join(random.choice(letters) for _ in range(length))
# Create a function to draw CAPTCHA image
def create_captcha(text, width=128, height=48, font_size=40, difficulty=2):
    image = Image.new('RGB', (width, height), color = (238, 170, 136))
    draw = ImageDraw.Draw(image)
    
    j=1
    for i in text:
        font = ImageFont.truetype("arial.ttf", random.randint(20,40))
        draw.text((j*24, random.randint(0,10)), i, fill=(128, 0, 0), font=font)
        j+=1
    
    # Adding some noise to the image
    for _ in range(random.randint(3*difficulty, 4*difficulty)):
        draw.line(((random.randint(0, width), random.randint(0, height)),(random.randint(0, width), random.randint(0, height))), fill=(128,0,0))
    
    image2 = Image.new('RGB', (width, height), color = (238, 170, 136))
    scale=random.randint(0,90/difficulty)+15
    scale2=random.randint(-60*difficulty,60*difficulty)
    offset2=random.randint(1,1000)
    for y in range(48):
        offset=(math.sin(y/(scale/12)+offset2)*scale2+math.cos(y/(scale/18)+offset2+42069)*(scale2))
        for x in range(128):
            offset3=(math.sin(x/(scale/7)+offset2*2)*scale2+math.cos(x/(scale/12)+offset2+6969420)*(scale2))
            color=image.getpixel((x, int(y+offset3/32)%48))
            if color[0]>=50:
                image2.putpixel((x, y), color)
            else:
                if random.randint(0,7)!=0:
                    col=min(abs(int((offset3)*12))+1,75)
                    image2.putpixel((x, y), (col,col,col))

    return image2