import os
import sys
from glif import parse_svg, glif2svg, glif2glif

if len(sys.argv) != 2:
    print("svg2glif filename")
    sys.exit(1)

filename_in  = sys.argv[1]
filename_out_svg = os.path.splitext(os.path.basename(filename_in))[0] + "_out3.svg"
print(f"{filename_in} -> {filename_out_svg}")
g = parse_svg(open(filename_in).read())
open(filename_out_svg, "w").write(glif2svg(g, False, True, 0.0))

filename_out_glif = os.path.splitext(os.path.basename(filename_in))[0] + "_out3.glif"
print(f"{filename_in} -> {filename_out_glif}")
g = parse_svg(open(filename_in).read())
open(filename_out_glif, "w").write(glif2glif(g))
