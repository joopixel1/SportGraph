#!/bin/bash
set -e

APP_DIR="/opt/SportGraph/api/src"
VENV_DIR="/opt/SportGraph/venv"

echo ">>> Pulling latest code"
cd $APP_DIR
git pull origin main

echo ">>> Installing dependencies"
$VENV_DIR/bin/pip install -r requirements.txt

echo ">>> Restarting service"
sudo systemctl restart sportgraph

echo ">>> Deployment complete!"
sudo systemctl status sportgraph --no-pager

