# Lighthouse-robot: Python met Chromium (Playwright). Zie src/hotel_checkin/robot.py.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir "playwright==1.63.0" ".[storage]"

ENV PYTHONUNBUFFERED=1 \
    HOTELS_CONFIG_DIR=/app/config/hotels \
    LIGHTHOUSE_STATE_DIR=/tmp/lighthouse
ENTRYPOINT ["python", "-m", "hotel_checkin.robot"]
