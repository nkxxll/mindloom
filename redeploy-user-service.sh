#!/bin/bash
set -e

cp mindloom.user.service ~/.config/systemd/user/mindloom.service

echo "Reloading mindloom service..."
systemctl --user daemon-reload

echo "Stopping mindloom service..."
systemctl --user stop mindloom

echo "Starting mindloom service..."
systemctl --user start mindloom

echo "Checking status..."
systemctl --user status mindloom
