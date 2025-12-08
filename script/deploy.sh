#!/bin/bash
set -e

APP_DIR="/opt/SportGraph/api/src"
VENV_DIR="/opt/SportGraph/.venv"

echo ">>> Pulling latest code"
cd $APP_DIR
git pull --rebase origin main

echo ">>> Installing dependencies"
make venv-install

echo ">>> Restarting service"
sudo systemctl restart sportgraph

echo ">>> Deployment complete!"
sudo systemctl status sportgraph --no-pager

