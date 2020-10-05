#!/bin/bash
if [ -f dist ]; then
    rm -r dist
fi

python3 setup.py sdist
sleep 2

cd dist

tar zxvf *.tar.gz
cd sylk_pushserver-?.?.?
ls
sleep 3

debuild --no-sign

ls
