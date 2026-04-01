FROM python:3.13-slim

WORKDIR /app

# System deps for audio analysis (ffmpeg) and Ed25519 (cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
COPY RESONANCE.json ./
COPY data/ ./data/

RUN pip install --no-cache-dir -e ".[telegram]"

# Default: serve v2
EXPOSE 7331
CMD ["python", "-c", "from seif.cli.wrapper import main; import sys; sys.argv=['seif','serve','--v2','--host','0.0.0.0']; main()"]
