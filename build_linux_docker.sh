#!/bin/bash
# Build Linux executable using Docker

echo "Building Linux executable with Docker..."

cd "$(dirname "$0")"

# Create Dockerfile for build
cat > Dockerfile.build << 'DOCKERFILE'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libxcb-cursor0 \
    libxkbcommon0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libdbus-1-3 \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyinstaller

COPY . .
RUN python build.py

CMD ["cp", "-r", "/app/output/builds/linux", "/output"]
DOCKERFILE

# Build in Docker
docker build -f Dockerfile.build -t local-print-builder .

# Extract the built executable
mkdir -p output/builds/linux
docker run --rm -v "$(pwd)/output/builds/linux:/output" local-print-builder

echo ""
echo "Build complete! Output: output/builds/linux/LocalPrintAgent"

# Cleanup
rm -f Dockerfile.build
