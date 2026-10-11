FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY sim/ sim/
RUN pip install --no-cache-dir ".[aws,history]" && useradd --system --uid 10001 sim

COPY data/ data/

USER sim
ENV LINES_FILE=/app/data/lines.yaml NETWORK_FILE=/app/data/network.json
# CMD (not ENTRYPOINT) so `aws ecs run-task` can override it to run sim.backfill
CMD ["python", "-m", "sim.service"]
