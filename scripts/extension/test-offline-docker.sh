#!/usr/bin/env bash
# A disposable Linux browser with synthetic data only. No host ports, .env,
# databases, personal browser directories, or writable repository mounts.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/../.." && pwd)"
extension_dir="$repo_dir/apps/extension/dist"
test -f "$extension_dir/manifest.json"
image_name="oscar-extension-test:playwright-1.51.1"
docker build --file "$script_dir/test-offline.Dockerfile" --tag "$image_name" "$script_dir"
docker run --rm --init --network none --shm-size=512m --pids-limit=256 \
  --cap-drop=ALL --security-opt=no-new-privileges --read-only \
  --tmpfs /tmp:rw,exec,nosuid,size=768m --tmpfs /root/.cache:rw,nosuid,size=64m \
  --tmpfs /root/.config:rw,nosuid,size=64m --tmpfs /root/.pki:rw,nosuid,size=16m \
  --mount "type=bind,src=$extension_dir,dst=/extension,readonly" \
  --mount "type=bind,src=$script_dir/test-offline.cjs,dst=/tests/test-offline.cjs,readonly" \
  "$image_name"
