#!/bin/bash

pyinstaller src/autoreply.py -n Autoreply -i icon.ico -w -y --clean --add-data "src/icon.png:." "$@"
