# Slabikář Font

This is an OpenType font (OTF) version of the Slabikář font from Petr Olšák:

http://petr.olsak.net/ftp/olsak/slabikar/

The `Slabikar.otf` font works in LaTeX, HTML, system-wide and it should work on
any system and program that works with OTF fonts.

# Examples

* LaTeX: [example.tex](./examples/tex/example.tex) ([example.pdf](./examples/tex/example.pdf))
* Online demo: https://certik.github.io/slabikar-otf/

# Build Instructions

To build the `Slabikar.otf` font from source:
```
conda env create -f environment.yml
conda activate fonts
./build.sh
```

To install system-wide on macOS, do:
```
cp Slabikar.otf ~/Library/Fonts
```
Then open up some text editor, such as Pages, and select the font
"Slabikář" and use it. Similarly on other systems.


# License

The Slabikář font shapes were created by Petr Olšák in Metafont and copyrighted
by him.

All the files in this repository were created by Ondřej Čertík and are licensed
under the MIT license, see [LICENSE](./LICENSE) file for more information.
