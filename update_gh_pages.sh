#!/bin/bash

set -ex

mkdir docs2
cp Slabikar.otf docs2/
cp examples/html/example.html docs2/index.html
git checkout gh-pages
rm -rf docs
mv docs2 docs
