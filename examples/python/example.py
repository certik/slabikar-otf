"""
Pillow has ImageFont for rendering text:

https://pillow.readthedocs.io/en/stable/reference/ImageFont.html

If Pillow is compiled without "RAQM" support, it can only print the glyphs from
`Slabikar.otf`, but does not execute/interpret the GSUB/GPOS tables, so the
beginning, end and middle connections are missing.

In order to get the proper text, we have to use Pillow with RAQM. To be
specific, the FreeType [1] library only handles glyph drawing, the HarfBuzz
library handles "text shaping" (the GSUB/GPOS tables in the OTF font) and
finally the RAQM [3] library provides a convenient API to FreeType+HarfBuzz.

[1] https://freetype.org/
[2] https://harfbuzz.github.io/
[3] https://github.com/HOST-Oman/libraqm
"""
import PIL.features
if not PIL.features.check_feature("raqm"):
    print("Warning: RAQM support is missing, the font will be incorrectly connected")
from PIL import Image, ImageFont, ImageDraw
antialiasing = True
scale=1
image = Image.new(mode="L" if antialiasing else "1",
        size=(80*scale, 33*scale), color="white")
draw = ImageDraw.Draw(image)
font = ImageFont.truetype("../../Slabikar.otf", 50*scale)
draw.text((3*scale, 2*scale), "Psát", font=font, fill='black')
image.save("font.png")
