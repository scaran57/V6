from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (900, 500), color=(255, 255, 255))
draw = ImageDraw.Draw(img)

# Text content simulating bookmaker screenshot
text = """
PREMIER LEAGUE

MANCHESTER UNITED   2
CHELSEA FC          1

Full Time
Odds:
Home: 1.62   Draw: 3.40   Away: 5.80

Score Correct:
2-1: 8.50
1-0: 7.20
2-0: 9.00
1-1: 6.80
0-0: 12.00
"""

draw.text((40, 40), text, fill=(0, 0, 0))

img.save("/app/test_images/ocr_test_premierleague.jpg")
print("✅ Image test créée: /app/test_images/ocr_test_premierleague.jpg")
