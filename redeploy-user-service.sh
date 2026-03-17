#!/bin/bash
set -e

echo "Stopping mindloom service..."
systemctl --user stop mindloom

echo "Copying files to ~/git/mindloom..."
mkdir -p ~/git/mindloom
rsync -av --delete --exclude='.git' --exclude='.venv' --exclude='__pycache__' . ~/git/mindloom/

echo "Starting mindloom service..."
systemctl --user start mindloom

echo "Checking status..."
systemctl --user status mindloom
