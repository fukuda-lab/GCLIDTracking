#!/bin/bash

set -e

echo "=== Update system ==="
sudo apt update -y
sudo apt upgrade -y

echo "=== Install packages ==="
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    unzip \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    xvfb \
    x11-utils

echo "=== Verify Python version ==="
python3 --version
pip3 --version

echo "=== Install Google Chrome Stable ==="
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list

sudo apt update -y
sudo apt install -y google-chrome-stable

google-chrome --version

echo "=== Check Chrome ==="
which google-chrome || which google-chrome-stable

echo "=== Setup Selenium & undetected-chromedriver ==="
pip3 install --upgrade pip
pip3 install selenium undetected-chromedriver
pip3 install -r requirements.txt

echo "=== !! Install finished !! ==="

