#!/usr/bin/env bash
# OmniVault Top-Level Launcher Script
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/desktop/run.sh" "$@"
