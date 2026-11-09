# Reuse the already installed Chromium revision; match its Playwright package.
FROM oscar-extension-test:playwright-1.51.1

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm install --prefix /opt/oscar --no-audit --no-fund --ignore-scripts @playwright/test@1.51.1

WORKDIR /opt/oscar/apps/web
ENV SIMULATION_EXTERNAL_SERVER=1 \
    SIMULATION_API_ORIGIN=http://127.0.0.1:8001

# Keep tmpfs artifacts available until the runner exports them after testing.
CMD ["sleep", "infinity"]
