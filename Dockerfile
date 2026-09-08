# =====================================================================
# Dungeon RPG - Dockerfile
#
# Packages the Textual terminal game into a small, reproducible Linux
# container. Built as a learning example for Docker/containerization:
#   1. Start from a slim, official Python base image.
#   2. Install only the dependencies listed in requirements.txt.
#   3. Copy in the application source.
#   4. Run the game as the container's default command.
#
# Build:  docker build -t dungeon-rpg .
# Run:    docker run -it dungeon-rpg
#         (the -it flags are required: the game is an interactive
#          terminal UI and needs an allocated TTY + stdin)
# =====================================================================

FROM python:3.13-slim

# Metadata (optional but good practice for real-world images).
LABEL maintainer="dungeon-rpg" \
      description="Terminal Dungeon Crawler RPG built with Textual"

# Ensure Python output is sent straight to the terminal without
# buffering, and that the terminal advertises color support so the
# Textual UI renders correctly.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TERM=xterm-256color

# Set the working directory inside the container.
WORKDIR /app

# Install dependencies first (separate layer) so Docker can cache this
# step and only re-run pip install when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source into the image.
COPY main.py .

# The SQLite save file will be created here at runtime. Declaring it
# as a volume lets a user persist saves across container runs with:
#   docker run -it -v dungeon-save:/app dungeon-rpg
VOLUME ["/app"]

# Run as a non-root user for better container security hygiene.
RUN useradd --create-home --shell /bin/bash player \
    && chown -R player:player /app
USER player

# Launch the game automatically when the container starts.
CMD ["python", "main.py"]
