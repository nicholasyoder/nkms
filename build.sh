#!/bin/bash

rm -rf ./build
mkdir ./build
rsync -av --delete --exclude='.idea' --exclude='.venv' --exclude='__pycache__' --exclude='build' ./ ./build/nkms/
cd ./build/nkms
dpkg-buildpackage -us -uc

echo -e "\nBuild finished. Check the ./build directory for packages."
