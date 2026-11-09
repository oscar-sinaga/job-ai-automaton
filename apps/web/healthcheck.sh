#!/usr/bin/env bash
set -euo pipefail
path=${1:-/manifest.webmanifest}
port=${2:-5173}
exec 3<>"/dev/tcp/127.0.0.1/$port"
printf 'GET %s HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' "$path" >&3
IFS= read -r status <&3
[[ "$status" == *' 200 '* ]]
