#!/usr/bin/env bash
# Real API + production web + Chromium, with fictional data and an offline LLM.
# Every runtime shares a new network-none namespace. No host ports, private env,
# user profile, existing database, or writable source mount enters this run.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/../.." && pwd)"
browser_image="oscar-browser-test:playwright-1.51.1"
browser_base="oscar-extension-test:playwright-1.51.1"
api_image="oscar-browser-api-test:local"
web_image="oscar-browser-web-test:local"

if [[ "${1:-}" != "" && "${1:-}" != "--prepare" ]]; then
  echo 'Usage: test-browser-docker.sh [--prepare]' >&2
  exit 2
fi
if ! docker image inspect "$browser_base" >/dev/null 2>&1; then
  docker build --file "$repo_dir/scripts/extension/test-offline.Dockerfile" \
    --tag "$browser_base" "$repo_dir/scripts/extension"
fi
docker build --file "$script_dir/test-browser.Dockerfile" --tag "$browser_image" "$script_dir"
if [[ "${1:-}" == "--prepare" ]]; then
  echo 'Browser test image ready; API/web sources have not been built or started.'
  exit 0
fi

# Repository .dockerignore excludes env files, databases, PDFs, logs and backups.
docker build --file "$repo_dir/apps/api/Dockerfile" --tag "$api_image" "$repo_dir"
docker build --file "$repo_dir/apps/web/Dockerfile" --tag "$web_image" "$repo_dir"

run_id="$(date -u +%Y%m%d%H%M%S)-$$"
prefix="oscar-browser-$run_id"
database="oscar_simulation_browser_${run_id//-/_}"
evidence_dir="$repo_dir/var/logs/browser-workflow-$run_id"
mkdir -p -- "$evidence_dir"
owned=()
browser_id=""

cleanup() {
  local status=$?
  trap - EXIT
  if [[ "$browser_id" =~ ^[a-f0-9]{64}$ ]] && [[ "$(docker inspect --format '{{index .Config.Labels "com.oscar.test-run"}}' "$browser_id" 2>/dev/null || true)" == "$run_id" ]]; then
    # Read tmpfs from inside the running container; Docker's archive endpoint
    # can omit tmpfs mounts. Extract a tar stream to avoid NTFS copyFile limits.
    docker exec "$browser_id" tar -C /evidence -cf - . \
      | tar --extract --file=- --directory="$evidence_dir" --no-same-owner --no-same-permissions \
      || status=1
    if [[ "$status" == 0 && "$(find "$evidence_dir" -type f -name simulation-cv.pdf -printf '.' | wc -c)" != 2 ]]; then
      echo 'Expected both desktop and mobile downloaded PDFs in the exported evidence.' >&2
      status=1
    fi
  fi
  for ((index=${#owned[@]}-1; index>=0; index--)); do
    local id="${owned[index]}"
    # Remove exact IDs created by this process only, after checking their label.
    if [[ "$id" =~ ^[a-f0-9]{64}$ ]] && [[ "$(docker inspect --format '{{index .Config.Labels "com.oscar.test-run"}}' "$id" 2>/dev/null || true)" == "$run_id" ]]; then
      docker logs "$id" > "$evidence_dir/$index.log" 2>&1 || true
      docker rm --force "$id" >/dev/null || status=1
    fi
  done
  echo "Synthetic browser evidence: $evidence_dir"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_owned() {
  local name=$1
  shift
  last_container_id="$(docker create --name "$name" --label "com.oscar.test-run=$run_id" "$@")"
  owned+=("$last_container_id")
  docker start "$last_container_id" >/dev/null
}
wait_ready() {
  local id=$1
  local description=$2
  shift 2
  for attempt in {1..90}; do
    if docker exec "$id" "$@" >/dev/null 2>&1; then
      echo "$description ready."
      return 0
    fi
    if [[ "$(docker inspect --format '{{.State.Running}}' "$id")" != true ]]; then
      docker logs --tail 80 "$id" >&2
      echo "$description stopped before becoming ready." >&2
      return 1
    fi
    sleep 1
  done
  echo "Timed out waiting for $description." >&2
  return 1
}

# The password below is a fixed synthetic fixture, unrelated to pilot secrets.
# PostgreSQL storage lives only in this new container's memory filesystem.
start_owned "$prefix-db" --network none --pids-limit=128 --memory=512m \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,size=384m \
  --env POSTGRES_USER=oscar --env POSTGRES_PASSWORD=simulation-postgres-only \
  --env "POSTGRES_DB=$database" postgres:16
db_id=$last_container_id
wait_ready "$db_id" PostgreSQL pg_isready -h 127.0.0.1 -U oscar -d "$database"

start_owned "$prefix-api" --network "container:$db_id" --init --pids-limit=128 \
  --read-only --tmpfs /tmp:rw,nosuid,size=32m \
  --tmpfs /data/pdfs:rw,nosuid,size=512m \
  --env PYTHONDONTWRITEBYTECODE=1 --env OPENAI_API_KEY= \
  "$api_image" python scripts/serve_simulation.py \
  --database-url "postgresql+psycopg://oscar:simulation-postgres-only@127.0.0.1:5432/$database" \
  --storage-dir /data/pdfs --port 8001
api_id=$last_container_id
wait_ready "$api_id" 'Simulation API' python -c \
  'import json,urllib.request; r=json.load(urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=2)); assert r["env"] == "simulation" and r["db"] == "ok"'

start_owned "$prefix-web" --network "container:$db_id" --init --pids-limit=128 \
  --read-only --tmpfs /tmp:rw,nosuid,size=64m \
  --env HOST=127.0.0.1 --env PORT=5173 --env ORIGIN=http://127.0.0.1:5173 \
  --env API_BASE_URL=http://127.0.0.1:8001/api/v1 --env API_KEY=simulation-only-key \
  --env OSCAR_APP_MODE=simulation "$web_image"
web_id=$last_container_id
wait_ready "$web_id" 'Production web' node -e \
  'fetch("http://127.0.0.1:5173/jobs").then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))'

browser_id="$(docker create --name "$prefix-browser" --label "com.oscar.test-run=$run_id" \
  --network "container:$db_id" --init --shm-size=512m --pids-limit=256 \
  --cap-drop=ALL --security-opt=no-new-privileges --read-only \
  --tmpfs /tmp:rw,exec,nosuid,size=768m --tmpfs /root/.cache:rw,nosuid,size=64m \
  --tmpfs /root/.config:rw,nosuid,size=64m --tmpfs /root/.pki:rw,nosuid,size=16m \
  --tmpfs /evidence:rw,nosuid,size=256m \
  --env SIMULATION_API_KEY=simulation-only-key \
  --mount "type=bind,src=$repo_dir/apps/web/tests/simulation,dst=/opt/oscar/apps/web/tests/simulation,readonly" \
  --mount "type=bind,src=$repo_dir/apps/web/playwright.config.ts,dst=/opt/oscar/apps/web/playwright.config.ts,readonly" "$browser_image")"
owned+=("$browser_id")
echo 'Running desktop/mobile browser regressions with the real isolated API.'
docker start "$browser_id" >/dev/null
set +e
docker exec "$browser_id" timeout --signal=TERM --kill-after=10s 600s \
  /opt/oscar/node_modules/.bin/playwright test --config=playwright.config.ts --output=/evidence/test-results \
  2>&1 | tee "$evidence_dir/playwright.log"
browser_status=${PIPESTATUS[0]}
set -e
exit "$browser_status"
