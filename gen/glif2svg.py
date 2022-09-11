import os
import sys
from glif import parse_glif, glif2svg

if len(sys.argv) != 2:
    print("glif2svg filename")
    sys.exit(1)

filename_in  = sys.argv[1]
filename_out_svg = os.path.splitext(os.path.basename(filename_in))[0] + ".svg"
print(f"{filename_in} -> {filename_out_svg}")
g = parse_glif(open(filename_in).read())
open(filename_out_svg, "w").write(glif2svg(g, False, True, 0.0))
