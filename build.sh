#!/bin/bash

set -ex

cd gen
python svg.py
cd ..

rm -rf tmp
checkoutlinesufo -e font.ufo -o tmp
psautohint tmp
makeotf -r -gs -omitMacNames -f tmp

cd examples/tex
cp ../../Slabikar.otf .
tectonic example.tex

gs \
    -q \
    -dNOPAUSE \
    -dBATCH \
    -sDEVICE=pngmono \
    -g2550x3300 \
    -dPDFFitPage \
    -dUseCropBox \
    -sOutputFile=example%d.png \
    example.pdf

python compare.py
