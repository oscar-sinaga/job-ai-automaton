# Keep the browser revision aligned with apps/web/package-lock.json.
FROM mcr.microsoft.com/playwright:v1.51.1-noble

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm install --prefix /opt/oscar --no-audit --no-fund --ignore-scripts playwright@1.51.1 \
    && apt-get update \
    && apt-get install -y --no-install-recommends xdotool \
    && rm -rf /var/lib/apt/lists/*

ENV PLAYWRIGHT_MODULE_PATH=/opt/oscar/node_modules/playwright \
    EXTENSION_PATH=/extension \
    EXTENSION_NATIVE_ACTION=1

CMD ["timeout", "--signal=TERM", "--kill-after=10s", "180s", "xvfb-run", "-a", "-e", "/dev/stderr", "-s", "-screen 0 1280x820x24", "node", "/tests/test-offline.cjs"]
