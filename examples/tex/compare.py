from PIL.Image import open
from PIL.ImageChops import difference

def images_equal(img1, img2, diff):
    d = difference(open(img1), open(img2))
    if d.getbbox():
        d.save(diff)
        # Images not equal
        return False
    else:
        # Images equal
        return True

if __name__ == '__main__':
    r1 = images_equal("example1.png", "reference/example1.png", "diff1.png")
    r2 = images_equal("example2.png", "reference/example2.png", "diff2.png")
    if r1 and r2:
        print("Images equal")
    else:
        print("Images NOT equal")
        raise Exception("Images not equal")
