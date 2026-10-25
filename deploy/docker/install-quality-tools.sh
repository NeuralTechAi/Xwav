#!/bin/sh
set -eu
export PLAYWRIGHT_BROWSERS_PATH=/opt/xwav-quality/browsers
python -m pip install --no-cache-dir playwright==1.60.0
python -m playwright install --with-deps chromium
npm install --prefix /opt/xwav-quality --no-audit --no-fund axe-core@4.14.0
chmod -R a+rX /opt/xwav-quality
rm -rf /var/lib/apt/lists/*
