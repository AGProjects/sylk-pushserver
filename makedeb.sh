#!/bin/bash
if [ -f dist ]; then
    rm -r dist
fi

python setup.py sdist
sleep 2

cd dist

tar zxvf *.tar.gz
cd sylk_pushserver-?.?.?
ls
sleep 3

debuild

cd dist
ls
