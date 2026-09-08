# Dungeon RPG

A complete terminal-based dungeon crawler RPG, written in Python and built
with the [Textual](https://textual.textualize.io/) TUI framework. The
project doubles as a hands-on learning example for **Docker and
containerization**: it takes a real, stateful, interactive terminal
application and packages it into a portable, reproducible container image.

```
______                                  _____ _____________
|  _  \                                |  __ \  ___| ___ \
| | | |_   _ _ __   __ _  ___  ___  _ __| |  \/ |___| |_/ /
| | | | | | | '_ \ / _` |/ _ \/ _ \| '_ \ | __ \___ \|  __/
| |/ /| |_| | | | | (_| |  __/ (_) | | | | \_/ / \_/ / |
|___/  \__,_|_| |_|\__, |\___|\___/|_| |_|\____/\____/\_|
                     __/ |
                    |___/         A Terminal Dungeon Crawler
```

## Features

- **Procedurally generated dungeons** — every floor is a fresh layout of
  rooms connected by corridors, rendered in ASCII.
- **Turn-based combat** — attack, drink a potion, or attempt to flee.
- **Full RPG progression** — HP, Attack, Defense, XP, Gold, Level and Score,
  all displayed live in the sidebar.
- **Inventory system** — Health Potions, a Sword, and a Shield that can be
  equipped for combat bonuses.
- **Increasing difficulty** — each dungeon level is bigger and spawns
  tougher, higher-reward enemies.
- **Save / Load** — game progress is persisted to a local SQLite database
  (`game.db`).
- **Polished Textual UI** — a Main Menu, Game Screen, modal Combat window,
  modal Inventory window, and a Game Over screen.
- **Docker-ready** — runs identically on your machine or inside a
  container.

## Project Structure

```
.
├── main.py            # The entire game (single file, OOP design)
├── requirements.txt   # Python dependencies (Textual)
├── Dockerfile          # Container build instructions
└── README.md           # This file
```

## Requirements

- Python 3.13 (also works on any Python 3.10+ interpreter)
- A terminal that supports ANSI colors (any modern Linux terminal, iTerm2,
  Windows Terminal, etc.)
- [Docker](https://docs.docker.com/get-docker/) (optional, for containerized
  play)

## Installation (running locally, without Docker)

```bash
# 1. Clone or copy this project directory, then enter it
cd dungeon-rpg

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the game
python3 main.py
```

## Running with Docker

This is the primary, recommended way to run the game — it guarantees the
exact same environment every time, with no local Python setup required.

### 1. Build the image

```bash
docker build -t dungeon-rpg .
```

This will:

- Pull the official `python:3.13-slim` base image.
- Install the dependencies from `requirements.txt`.
- Copy `main.py` into the image.
- Configure the container to launch the game automatically.

### 2. Run the container

```bash
docker run -it dungeon-rpg
```

> **Important:** the `-it` flags are required. `-i` keeps STDIN open so
> your keyboard input reaches the game, and `-t` allocates a pseudo-TTY so
> the Textual interface can render correctly. Without them the game will
> not display or respond to input.

### 3. (Optional) Persist saves across container runs

By default, each `docker run` starts a fresh container filesystem, so a
save made inside one run won't be visible on the next unless you mount a
volume:

```bash
docker run -it -v dungeon-save:/app dungeon-rpg
```

This mounts a named Docker volume at `/app` inside the container, so
`game.db` survives between runs. You can inspect the volume with:

```bash
docker volume inspect dungeon-save
```

### Useful Docker commands while learning

```bash
docker images                 # see the built dungeon-rpg image
docker ps -a                  # see stopped/running containers
docker rm <container_id>      # remove a stopped container
docker rmi dungeon-rpg        # remove the image
docker build --no-cache -t dungeon-rpg .   # rebuild ignoring layer cache
```

## Gameplay

### The Map

Each dungeon floor is drawn in ASCII using these symbols:

| Symbol | Meaning        |
|:------:|----------------|
| `@`    | You (the player) |
| `#`    | Wall (impassable) |
| `.`    | Floor (walkable) |
| `E`    | Enemy          |
| `$`    | Treasure (gold) |
| `X`    | Exit (descend to the next level) |

### Controls

| Key(s)          | Action                        |
|------------------|-------------------------------|
| `↑ ↓ ← →`        | Move the player                |
| `i`              | Open Inventory                 |
| `s`              | Save game to `game.db`         |
| `l`              | Load game from `game.db`       |
| `Esc`            | Return to the Main Menu        |
| `q`              | Quit the application           |

During **combat**, use the on-screen buttons (or click with your
mouse/trackpad, which Textual supports even in the terminal) to:

- **Attack** — deal damage based on your Attack stat vs. the enemy's
  Defense.
- **Use Potion** — heal 50% of your max HP (consumes one potion).
- **Flee** — attempt to escape the fight (50% chance of success).

### Combat

Walking into an enemy tile doesn't move you onto it — instead it opens a
turn-based **Combat** window. Each round, damage dealt and damage received
are shown in the battle log. Defeating an enemy grants XP, gold, and a
score bonus, and has a chance to drop bonus loot (a potion, sword, or
shield).

### Leveling Up

Gaining enough XP levels you up automatically, which:

- Fully restores your HP
- Increases Max HP
- Increases Attack
- Increases Defense
- Raises the XP required for the next level

### Treasure & Gold

Walking onto a `$` tile automatically collects its gold, adds to your
Score, and the treasure disappears from the map.

### Inventory & Equipment

Press `i` at any time during gameplay to open your Inventory:

- **Health Potions** restore 50% of your max HP when used.
- **Sword** — equip for a permanent **+3 Attack** bonus in combat.
- **Shield** — equip for a permanent **+2 Defense** bonus in combat.

Swords and shields are found as rare enemy loot drops after combat
victories.

### Dungeon Progression

Reaching the `X` exit tile immediately generates a brand-new, larger
dungeon with more (and stronger) enemies and more treasure, and increments
your dungeon level counter.

### Save & Load

- Press `s` during gameplay to save your Player stats (HP, Attack,
  Defense, XP, Gold, Level, Score), current dungeon level, and full
  Inventory to a local SQLite database file, `game.db`.
- Press `l` to load your most recent save. Loading regenerates a fresh
  layout for your saved dungeon level (enemies and treasure respawn), so
  you always return to a full, playable floor.

### Game Over

If your HP reaches 0, the **Game Over** screen appears showing your final
Score and the dungeon level you reached, with options to:

- **Restart** — begin a brand-new game immediately.
- **Quit** — exit the application.

## How This Project Teaches Docker

This repository is intentionally structured to demonstrate core
containerization concepts:

1. **Reproducible environments** — `requirements.txt` pins the exact
   dependency needed (`textual`), so `pip install -r requirements.txt`
   produces the same environment anywhere.
2. **Layered builds** — the `Dockerfile` copies `requirements.txt` and
   installs dependencies *before* copying `main.py`, so Docker's build
   cache avoids re-installing dependencies every time you only change game
   code.
3. **Minimal base images** — `python:3.13-slim` keeps the final image
   small compared to the full `python:3.13` image.
4. **Least-privilege containers** — the game runs as a dedicated non-root
   `player` user inside the container rather than root.
5. **Interactive containers** — running a TUI app in Docker requires
   understanding `-it` (interactive + TTY), a common point of confusion
   for newcomers to Docker.
6. **Volumes for persistence** — since containers are ephemeral by
   default, the README shows how to use a named volume to persist the
   SQLite save file across runs.

## Troubleshooting

- **The game looks garbled or colors are missing in Docker.** Make sure
  your host terminal itself supports ANSI/256 colors, and that you used
  `docker run -it` (not just `-i` or just `-t`).
- **Keyboard input doesn't seem to register.** Ensure the container has an
  allocated TTY (`-t`) and that STDIN is attached (`-i`). Some CI/remote
  shells strip TTY allocation by default.
- **`game.db` disappears after `docker run`.** This is expected — each
  container has its own filesystem. Use the volume-mount instructions
  above to persist saves.
