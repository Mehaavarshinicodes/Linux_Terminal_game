#!/usr/bin/env python3
"""
=====================================================================
 DUNGEON RPG - A Terminal Dungeon Crawler built with Textual
=====================================================================

A single-file, object-oriented dungeon crawler RPG designed to run
in a Linux terminal and inside a Docker container. Built to teach
containerization concepts (packaging a stateful, interactive TUI
application) alongside classic roguelike gameplay.

Features:
    - Procedurally generated dungeons (rooms + corridors)
    - Turn-based combat
    - Leveling / XP / Gold / Score systems
    - Inventory with potions, sword and shield equipment
    - SQLite-backed save / load system (game.db)
    - Full Textual TUI: Main Menu, Game Screen, Combat Modal,
      Inventory Modal, Game Over Screen

Run with:  python3 main.py
=====================================================================
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from rich.text import Text

from textual.app import App
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Header, Static


# =====================================================================
# CONSTANTS
# =====================================================================

WALL = "#"
FLOOR = "."
PLAYER_SYM = "@"
ENEMY_SYM = "E"
TREASURE_SYM = "$"
EXIT_SYM = "X"

DB_PATH = "game.db"

# Base stats a brand new hero starts with.
BASE_HP = 30
BASE_ATTACK = 5
BASE_DEFENSE = 2
BASE_XP_TO_NEXT = 20

# (name, base_hp, base_attack, base_defense, base_xp_reward, base_gold_reward)
ENEMY_TEMPLATES = [
    ("Goblin", 10, 3, 1, 8, 5),
    ("Skeleton", 14, 4, 2, 12, 8),
    ("Giant Rat", 8, 2, 1, 5, 3),
    ("Orc Brute", 18, 5, 3, 16, 12),
    ("Dark Cultist", 12, 6, 1, 18, 15),
    ("Cave Troll", 25, 6, 4, 25, 20),
    ("Shadow Wraith", 16, 7, 2, 22, 18),
]

TITLE_ART = r"""
______                                  _____ _____________
|  _  \                                |  __ \  ___| ___ \
| | | |_   _ _ __   __ _  ___  ___  _ __| |  \/ |___| |_/ /
| | | | | | | '_ \ / _` |/ _ \/ _ \| '_ \ | __ \___ \|  __/
| |/ /| |_| | | | | (_| |  __/ (_) | | | | \_/ / \_/ / |
|___/  \__,_|_| |_|\__, |\___|\___/|_| |_|\____/\____/\_|
                     __/ |
                    |___/         A Terminal Dungeon Crawler
"""


# =====================================================================
# MODEL: PLAYER
# =====================================================================

class Player:
    """Represents the hero controlled by the user.

    Holds all RPG stats (HP, attack, defense, XP, gold, level, score)
    as well as the inventory of items the player has collected.
    """

    def __init__(self) -> None:
        self.name = "Hero"
        self.hp = BASE_HP
        self.max_hp = BASE_HP
        self.attack = BASE_ATTACK
        self.defense = BASE_DEFENSE
        self.xp = 0
        self.xp_to_next = BASE_XP_TO_NEXT
        self.gold = 0
        self.level = 1
        self.score = 0

        # Position on the current dungeon grid.
        self.x = 0
        self.y = 0

        # Inventory: simple counters for consumables / equipment owned.
        self.inventory = {
            "potions": 2,
            "swords": 0,
            "shields": 0,
        }
        self.sword_equipped = False
        self.shield_equipped = False

    # -- derived stats --------------------------------------------------

    @property
    def total_attack(self) -> int:
        """Attack including equipped weapon bonus."""
        return self.attack + (3 if self.sword_equipped else 0)

    @property
    def total_defense(self) -> int:
        """Defense including equipped shield bonus."""
        return self.defense + (2 if self.shield_equipped else 0)

    # -- behaviour --------------------------------------------------------

    def gain_xp(self, amount: int) -> bool:
        """Add XP, applying as many level-ups as are earned.

        Returns True if at least one level-up occurred.
        """
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self._level_up()
            leveled = True
        return leveled

    def _level_up(self) -> None:
        """Increase core stats and fully heal on level up."""
        self.level += 1
        self.max_hp += 10
        self.hp = self.max_hp
        self.attack += 2
        self.defense += 1
        self.xp_to_next = int(self.xp_to_next * 1.5)

    def use_potion(self) -> int:
        """Consume one potion if available, healing 50% of max HP.

        Returns the amount healed (0 if no potions available).
        """
        if self.inventory["potions"] <= 0:
            return 0
        self.inventory["potions"] -= 1
        heal = max(1, int(self.max_hp * 0.5))
        before = self.hp
        self.hp = min(self.max_hp, self.hp + heal)
        return self.hp - before

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage (already reduced by defense) and clamp at 0."""
        amount = max(0, amount)
        self.hp = max(0, self.hp - amount)
        return amount

    # -- persistence --------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "xp": self.xp,
            "xp_to_next": self.xp_to_next,
            "gold": self.gold,
            "level": self.level,
            "score": self.score,
            "inventory": dict(self.inventory),
            "sword_equipped": self.sword_equipped,
            "shield_equipped": self.shield_equipped,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        p = cls()
        p.name = data.get("name", "Hero")
        p.hp = data["hp"]
        p.max_hp = data["max_hp"]
        p.attack = data["attack"]
        p.defense = data["defense"]
        p.xp = data["xp"]
        p.xp_to_next = data["xp_to_next"]
        p.gold = data["gold"]
        p.level = data["level"]
        p.score = data["score"]
        p.inventory = dict(data["inventory"])
        p.sword_equipped = data["sword_equipped"]
        p.shield_equipped = data["shield_equipped"]
        return p


# =====================================================================
# MODEL: ENEMY
# =====================================================================

class Enemy:
    """A monster that can be encountered inside a dungeon."""

    def __init__(self, name: str, hp: int, attack: int, defense: int,
                 xp_reward: int, gold_reward: int) -> None:
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.attack = attack
        self.defense = defense
        self.xp_reward = xp_reward
        self.gold_reward = gold_reward
        self.x = 0
        self.y = 0

    def is_alive(self) -> bool:
        return self.hp > 0

    @staticmethod
    def spawn(dungeon_level: int) -> "Enemy":
        """Create a new enemy, scaled in difficulty by dungeon level."""
        name, hp, atk, dfn, xp, gold = random.choice(ENEMY_TEMPLATES)
        mult = 1 + (dungeon_level - 1) * 0.3
        return Enemy(
            name=name,
            hp=max(4, int(hp * mult)),
            attack=max(1, int(atk * mult)),
            defense=max(0, int(dfn * mult)),
            xp_reward=max(1, int(xp * mult)),
            gold_reward=max(1, int(gold * mult)),
        )


# =====================================================================
# MODEL: DUNGEON (procedural generation)
# =====================================================================

class Dungeon:
    """A single procedurally generated dungeon level.

    Generation strategy: carve a handful of random rectangular rooms
    into a solid wall grid, then connect consecutive room centers with
    L-shaped corridors. This guarantees every room is reachable from
    the start room. Enemies and treasure are then scattered on free
    floor tiles.
    """

    def __init__(self, level: int) -> None:
        self.level = level
        # Dungeons get modestly larger and busier as the player
        # descends deeper, increasing difficulty over time.
        self.width = min(70, 46 + level * 2)
        self.height = min(24, 14 + level)

        self.grid = [[WALL for _ in range(self.width)] for _ in range(self.height)]
        self.rooms: list[tuple[int, int, int, int]] = []
        self.enemies: list[Enemy] = []
        self.treasures: dict[tuple[int, int], int] = {}
        self.start = (1, 1)
        self.exit = (self.width - 2, self.height - 2)

        self._generate()

    # -- generation --------------------------------------------------------

    def _generate(self) -> None:
        num_rooms = random.randint(6, 10)
        for _ in range(num_rooms):
            w = random.randint(4, 8)
            h = random.randint(3, 6)
            max_x = self.width - w - 2
            max_y = self.height - h - 2
            if max_x < 1 or max_y < 1:
                continue
            x = random.randint(1, max_x)
            y = random.randint(1, max_y)
            self._carve_room(x, y, w, h)
            self.rooms.append((x, y, w, h))

        # Fallback: guarantee at least one room exists.
        if not self.rooms:
            self._carve_room(1, 1, 4, 4)
            self.rooms.append((1, 1, 4, 4))

        # Connect every room to the next with a corridor so the whole
        # dungeon is guaranteed traversable.
        centers = [self._room_center(r) for r in self.rooms]
        for i in range(len(centers) - 1):
            self._carve_corridor(centers[i], centers[i + 1])

        self.start = centers[0]
        self.exit = centers[-1]

        self._populate(num_enemies=3 + self.level,
                        num_treasures=3 + self.level // 2)

    def _room_center(self, room: tuple[int, int, int, int]) -> tuple[int, int]:
        x, y, w, h = room
        return (x + w // 2, y + h // 2)

    def _carve_room(self, x: int, y: int, w: int, h: int) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.grid[yy][xx] = FLOOR

    def _carve_corridor(self, a: tuple[int, int], b: tuple[int, int]) -> None:
        x1, y1 = a
        x2, y2 = b
        if random.random() < 0.5:
            self._carve_h(x1, x2, y1)
            self._carve_v(y1, y2, x2)
        else:
            self._carve_v(y1, y2, x1)
            self._carve_h(x1, x2, y2)

    def _carve_h(self, x1: int, x2: int, y: int) -> None:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.grid[y][x] = FLOOR

    def _carve_v(self, y1: int, y2: int, x: int) -> None:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.grid[y][x] = FLOOR

    def _populate(self, num_enemies: int, num_treasures: int) -> None:
        floor_cells = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.grid[y][x] == FLOOR and (x, y) not in (self.start, self.exit)
        ]
        random.shuffle(floor_cells)

        enemy_cells = floor_cells[:num_enemies]
        treasure_cells = floor_cells[num_enemies:num_enemies + num_treasures]

        for (ex, ey) in enemy_cells:
            enemy = Enemy.spawn(self.level)
            enemy.x, enemy.y = ex, ey
            self.enemies.append(enemy)

        for (tx, ty) in treasure_cells:
            self.treasures[(tx, ty)] = random.randint(5, 15) * self.level

    # -- queries --------------------------------------------------------

    def is_wall(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return True
        return self.grid[y][x] == WALL

    def enemy_at(self, x: int, y: int) -> Enemy | None:
        for enemy in self.enemies:
            if enemy.is_alive() and enemy.x == x and enemy.y == y:
                return enemy
        return None

    def remaining_enemies(self) -> int:
        return sum(1 for e in self.enemies if e.is_alive())

    # -- rendering --------------------------------------------------------

    def render(self, player: Player) -> str:
        """Render the dungeon (with player, enemies, treasure) as ASCII."""
        enemy_positions = {
            (e.x, e.y) for e in self.enemies if e.is_alive()
        }
        lines = []
        for y in range(self.height):
            row_chars = []
            for x in range(self.width):
                if (x, y) == (player.x, player.y):
                    row_chars.append(PLAYER_SYM)
                elif (x, y) == self.exit:
                    row_chars.append(EXIT_SYM)
                elif (x, y) in enemy_positions:
                    row_chars.append(ENEMY_SYM)
                elif (x, y) in self.treasures:
                    row_chars.append(TREASURE_SYM)
                else:
                    row_chars.append(self.grid[y][x])
            lines.append("".join(row_chars))
        return "\n".join(lines)


# =====================================================================
# GAME STATE
# =====================================================================

class GameState:
    """Bundles the player and current dungeon into one session object."""

    def __init__(self) -> None:
        self.player = Player()
        self.dungeon_level = 1
        self.dungeon = Dungeon(self.dungeon_level)
        self.player.x, self.player.y = self.dungeon.start
        self.message = "Welcome, adventurer. Find the exit (X) to descend."

    def next_level(self) -> None:
        """Generate a new, harder dungeon and place the player at start."""
        self.dungeon_level += 1
        self.dungeon = Dungeon(self.dungeon_level)
        self.player.x, self.player.y = self.dungeon.start
        self.message = f"You descend to dungeon level {self.dungeon_level}!"


# =====================================================================
# PERSISTENCE: SQLITE SAVE MANAGER
# =====================================================================

class SaveManager:
    """Handles saving and loading game progress using SQLite.

    Only a single save slot is used (row id = 1) for simplicity, which
    keeps the schema tiny while still demonstrating full CRUD-style
    persistence backed by a real SQLite database file (game.db).
    """

    def __init__(self, path: str = DB_PATH) -> None:
        self.path = path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saves (
                    id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def save(self, state: GameState) -> None:
        payload = {
            "player": state.player.to_dict(),
            "dungeon_level": state.dungeon_level,
        }
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("DELETE FROM saves WHERE id = 1")
            conn.execute(
                "INSERT INTO saves (id, data, saved_at) VALUES (1, ?, ?)",
                (json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def load(self) -> GameState | None:
        conn = sqlite3.connect(self.path)
        try:
            cur = conn.execute("SELECT data FROM saves WHERE id = 1")
            row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        payload = json.loads(row[0])
        state = GameState.__new__(GameState)  # bypass __init__
        state.player = Player.from_dict(payload["player"])
        state.dungeon_level = payload["dungeon_level"]
        state.dungeon = Dungeon(state.dungeon_level)
        state.player.x, state.player.y = state.dungeon.start
        state.message = "Game loaded. A fresh layout awaits on this level."
        return state

    def has_save(self) -> bool:
        conn = sqlite3.connect(self.path)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM saves")
            count = cur.fetchone()[0]
        finally:
            conn.close()
        return count > 0


# =====================================================================
# UI HELPERS
# =====================================================================

def render_stats_panel(state: GameState) -> str:
    """Build the sidebar text showing stats, dungeon info and inventory."""
    p = state.player
    sword_line = (
        "Equipped" if p.sword_equipped
        else (f"Owned x{p.inventory['swords']}" if p.inventory["swords"] else "None")
    )
    shield_line = (
        "Equipped" if p.shield_equipped
        else (f"Owned x{p.inventory['shields']}" if p.inventory["shields"] else "None")
    )
    return (
        f"[b]== HERO ==[/b]\n"
        f"Level:    {p.level}\n"
        f"HP:       {p.hp}/{p.max_hp}\n"
        f"Attack:   {p.total_attack}\n"
        f"Defense:  {p.total_defense}\n"
        f"XP:       {p.xp}/{p.xp_to_next}\n"
        f"Gold:     {p.gold}\n"
        f"Score:    {p.score}\n"
        f"\n"
        f"[b]== DUNGEON ==[/b]\n"
        f"Floor:    {state.dungeon_level}\n"
        f"Enemies:  {state.dungeon.remaining_enemies()}\n"
        f"Treasure: {len(state.dungeon.treasures)}\n"
        f"\n"
        f"[b]== INVENTORY ==[/b]\n"
        f"Potions:  {p.inventory['potions']}\n"
        f"Sword:    {sword_line}\n"
        f"Shield:   {shield_line}\n"
        f"\n"
        f"[b]== LOG ==[/b]\n"
        f"{state.message}"
    )


LEGEND_TEXT = (
    "@ You   # Wall   . Floor   E Enemy   $ Treasure   X Exit\n"
    "Arrows: Move   i: Inventory   s: Save   l: Load   Esc: Menu   q: Quit"
)


# =====================================================================
# SCREEN: MAIN MENU
# =====================================================================

class MainMenuScreen(Screen):
    """The title / main menu screen shown at launch."""

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
    ]

    def compose(self):
        with Container(id="menu-container"):
            yield Static(TITLE_ART, id="menu-title")
            yield Static("A Terminal Dungeon Crawler", id="menu-subtitle")
            with Vertical(id="menu-buttons"):
                yield Button("New Game", id="new-game", variant="success")
                yield Button("Load Game", id="load-game", variant="primary")
                yield Button("Quit", id="quit", variant="error")
            yield Static("", id="menu-message")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-game":
            self.app.state = GameState()
            self.app.switch_screen(GameScreen())
        elif event.button.id == "load-game":
            loaded = self.app.save_manager.load()
            if loaded is not None:
                self.app.state = loaded
                self.app.switch_screen(GameScreen())
            else:
                self.query_one("#menu-message", Static).update(
                    "No saved game found. Start a New Game first."
                )
        elif event.button.id == "quit":
            self.app.exit()

    def action_quit_app(self) -> None:
        self.app.exit()


# =====================================================================
# SCREEN: GAME (main gameplay screen)
# =====================================================================

class GameScreen(Screen):
    """The primary gameplay screen: dungeon map + stats + controls."""

    BINDINGS = [
        Binding("up", "move_up", "Move Up", show=True),
        Binding("down", "move_down", "Move Down", show=True),
        Binding("left", "move_left", "Move Left", show=True),
        Binding("right", "move_right", "Move Right", show=True),
        Binding("w", "move_up", "Move Up", show=False),
        Binding("s", "save_game", "Save", show=True),
        Binding("a", "move_left", "Move Left", show=False),
        Binding("d", "move_right", "Move Right", show=False),
        Binding("i", "open_inventory", "Inventory", show=True),
        Binding("l", "load_game", "Load", show=True),
        Binding("escape", "back_to_menu", "Menu", show=True),
        Binding("q", "quit_app", "Quit", show=True),
    ]

    def compose(self):
        yield Header(show_clock=True)
        with Horizontal(id="game-body"):
            yield Static(id="map-view", classes="panel map-panel")
            with Vertical(id="side-panel"):
                yield Static(id="stats-view", classes="panel stats-panel")
                yield Static(LEGEND_TEXT, id="legend-view", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_display()

    # -- rendering --------------------------------------------------------

    def refresh_display(self) -> None:
        state = self.app.state
        map_text = Text(state.dungeon.render(state.player), no_wrap=True)
        self.query_one("#map-view", Static).update(map_text)
        self.query_one("#stats-view", Static).update(render_stats_panel(state))

    # -- movement --------------------------------------------------------

    def action_move_up(self) -> None:
        self.try_move(0, -1)

    def action_move_down(self) -> None:
        self.try_move(0, 1)

    def action_move_left(self) -> None:
        self.try_move(-1, 0)

    def action_move_right(self) -> None:
        self.try_move(1, 0)

    def try_move(self, dx: int, dy: int) -> None:
        state = self.app.state
        player = state.player
        dungeon = state.dungeon
        nx, ny = player.x + dx, player.y + dy

        # Walls block movement entirely.
        if dungeon.is_wall(nx, ny):
            return

        # Bumping into an enemy starts combat instead of moving onto it.
        enemy = dungeon.enemy_at(nx, ny)
        if enemy is not None:
            self.encounter_enemy(enemy)
            return

        # Collect treasure as we step onto it.
        if (nx, ny) in dungeon.treasures:
            gold = dungeon.treasures.pop((nx, ny))
            player.gold += gold
            player.score += gold
            state.message = f"You found {gold} gold!"

        player.x, player.y = nx, ny

        # Reaching the exit generates the next, harder dungeon.
        if (nx, ny) == dungeon.exit:
            state.next_level()

        self.refresh_display()

    # -- combat --------------------------------------------------------

    def encounter_enemy(self, enemy: Enemy) -> None:
        state = self.app.state

        def on_combat_end(result: str | None) -> None:
            if result == "death":
                self.app.switch_screen(
                    GameOverScreen(score=state.player.score, level=state.dungeon_level)
                )
            else:
                self.refresh_display()

        self.app.push_screen(CombatScreen(state.player, enemy), on_combat_end)

    # -- inventory --------------------------------------------------------

    def action_open_inventory(self) -> None:
        self.app.push_screen(
            InventoryScreen(self.app.state.player), lambda _: self.refresh_display()
        )

    # -- save / load --------------------------------------------------------

    def action_save_game(self) -> None:
        self.app.save_manager.save(self.app.state)
        self.app.state.message = "Game saved to game.db."
        self.refresh_display()

    def action_load_game(self) -> None:
        loaded = self.app.save_manager.load()
        if loaded is not None:
            self.app.state = loaded
            self.refresh_display()
        else:
            self.app.state.message = "No saved game found."
            self.refresh_display()

    # -- navigation --------------------------------------------------------

    def action_back_to_menu(self) -> None:
        self.app.switch_screen(MainMenuScreen())

    def action_quit_app(self) -> None:
        self.app.exit()


# =====================================================================
# SCREEN: COMBAT (modal)
# =====================================================================

class CombatScreen(ModalScreen[str]):
    """Turn-based combat modal, triggered when the player meets an enemy."""

    BINDINGS = [
        Binding("escape", "noop", "", show=False),
    ]

    def __init__(self, player: Player, enemy: Enemy) -> None:
        super().__init__()
        self.player = player
        self.enemy = enemy
        self.log_lines: list[str] = [f"A wild {enemy.name} blocks your path!"]
        self.combat_over = False

    def compose(self):
        with Container(id="combat-container"):
            yield Static("COMBAT", id="combat-title")
            yield Static(self._render_status(), id="combat-status")
            yield Static("\n".join(self.log_lines[-8:]), id="combat-log")
            with Horizontal(id="combat-buttons"):
                yield Button("Attack", id="attack", variant="error")
                yield Button("Use Potion", id="potion", variant="success")
                yield Button("Flee", id="flee", variant="warning")

    # -- rendering --------------------------------------------------------

    def _render_status(self) -> str:
        p, e = self.player, self.enemy
        return (
            f"{p.name}   HP: {p.hp}/{p.max_hp}   ATK: {p.total_attack}   DEF: {p.total_defense}\n"
            f"{e.name}   HP: {max(e.hp, 0)}/{e.max_hp}   ATK: {e.attack}   DEF: {e.defense}"
        )

    def _log(self, text: str) -> None:
        self.log_lines.append(text)
        self.query_one("#combat-log", Static).update("\n".join(self.log_lines[-8:]))
        self.query_one("#combat-status", Static).update(self._render_status())

    def _finish(self, result: str) -> None:
        # NOTE: called from a timer callback. We intentionally do not
        # return/await self.dismiss()'s result here -- Textual will try
        # to await whatever a timer callback returns, and awaiting
        # dismiss() from that context raises a ScreenError. Calling it
        # as a plain statement (return value discarded) avoids that.
        self.dismiss(result)

    def action_noop(self) -> None:
        # Escape is disabled during combat; you must Attack or Flee.
        pass

    # -- interaction --------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.combat_over:
            return
        if event.button.id == "attack":
            self._player_attack()
        elif event.button.id == "potion":
            self._use_potion()
        elif event.button.id == "flee":
            self._attempt_flee()

    def _player_attack(self) -> None:
        dmg = max(1, self.player.total_attack - self.enemy.defense + random.randint(-2, 2))
        self.enemy.hp -= dmg
        self._log(f"You strike the {self.enemy.name} for {dmg} damage.")
        if self.enemy.hp <= 0:
            self._victory()
            return
        self._enemy_turn()

    def _enemy_turn(self) -> None:
        dmg = max(1, self.enemy.attack - self.player.total_defense + random.randint(-2, 2))
        self.player.take_damage(dmg)
        self._log(f"{self.enemy.name} hits you for {dmg} damage.")
        if not self.player.is_alive():
            self._log("You have fallen in the dungeon...")
            self.combat_over = True
            self.set_timer(1.6, lambda: self._finish("death"))

    def _use_potion(self) -> None:
        healed = self.player.use_potion()
        if healed > 0:
            self._log(f"You drink a potion, healing {healed} HP.")
            self._enemy_turn()
        else:
            self._log("You have no potions left!")

    def _attempt_flee(self) -> None:
        if random.random() < 0.5:
            self._log("You escape successfully!")
            self.combat_over = True
            self.set_timer(1.0, lambda: self._finish("flee"))
        else:
            self._log("Your escape attempt failed!")
            self._enemy_turn()

    def _victory(self) -> None:
        self._log(f"You defeated the {self.enemy.name}!")
        self.player.gold += self.enemy.gold_reward
        self.player.score += self.enemy.gold_reward * 2
        leveled = self.player.gain_xp(self.enemy.xp_reward)
        self._log(f"+{self.enemy.xp_reward} XP, +{self.enemy.gold_reward} gold.")
        if leveled:
            self._log(f"Level up! You are now level {self.player.level}.")

        # Small chance of a bonus item drop.
        roll = random.random()
        if roll < 0.15:
            self.player.inventory["potions"] += 1
            self._log("The enemy dropped a Health Potion!")
        elif roll < 0.22:
            self.player.inventory["swords"] += 1
            self._log("The enemy dropped a Sword!")
        elif roll < 0.28:
            self.player.inventory["shields"] += 1
            self._log("The enemy dropped a Shield!")

        self.combat_over = True
        self.set_timer(1.6, lambda: self._finish("victory"))


# =====================================================================
# SCREEN: INVENTORY (modal)
# =====================================================================

class InventoryScreen(ModalScreen):
    """Modal for reviewing and using inventory items / equipment."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("i", "close", "Close", show=False),
    ]

    def __init__(self, player: Player) -> None:
        super().__init__()
        self.player = player

    def compose(self):
        with Container(id="inventory-container"):
            yield Static("INVENTORY", id="inventory-title")
            yield Static(self._render_body(), id="inventory-body")
            with Horizontal(id="inventory-buttons"):
                yield Button("Use Potion", id="use-potion", variant="success")
                yield Button("Equip Sword", id="equip-sword", variant="primary")
                yield Button("Equip Shield", id="equip-shield", variant="primary")
                yield Button("Close", id="close", variant="error")

    def _render_body(self) -> str:
        p = self.player
        return (
            f"Health Potions: {p.inventory['potions']}  (heals 50% max HP)\n"
            f"\n"
            f"Swords owned:  {p.inventory['swords']}   "
            f"Equipped: {'Yes (+3 ATK)' if p.sword_equipped else 'No'}\n"
            f"Shields owned: {p.inventory['shields']}   "
            f"Equipped: {'Yes (+2 DEF)' if p.shield_equipped else 'No'}\n"
            f"\n"
            f"Current Attack:  {p.total_attack}\n"
            f"Current Defense: {p.total_defense}\n"
            f"Current HP:      {p.hp}/{p.max_hp}"
        )

    def _refresh(self) -> None:
        self.query_one("#inventory-body", Static).update(self._render_body())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        p = self.player
        bid = event.button.id
        if bid == "use-potion":
            p.use_potion()
        elif bid == "equip-sword":
            if p.inventory["swords"] > 0:
                p.sword_equipped = not p.sword_equipped
        elif bid == "equip-shield":
            if p.inventory["shields"] > 0:
                p.shield_equipped = not p.shield_equipped
        elif bid == "close":
            self.dismiss()
            return
        self._refresh()

    def action_close(self) -> None:
        self.dismiss()


# =====================================================================
# SCREEN: GAME OVER
# =====================================================================

class GameOverScreen(Screen):
    """Shown when the player's HP reaches zero."""

    def __init__(self, score: int, level: int) -> None:
        super().__init__()
        self.score = score
        self.level = level

    def compose(self):
        with Container(id="gameover-container"):
            yield Static("GAME OVER", id="gameover-title")
            yield Static(
                f"Final Score: {self.score}\nDungeon Level Reached: {self.level}",
                id="gameover-stats",
            )
            with Horizontal(id="gameover-buttons"):
                yield Button("Restart", id="restart", variant="success")
                yield Button("Quit", id="quit", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "restart":
            self.app.state = GameState()
            self.app.switch_screen(GameScreen())
        else:
            self.app.exit()


# =====================================================================
# APPLICATION
# =====================================================================

class DungeonRPGApp(App):
    """The Textual application tying every screen together."""

    TITLE = "Dungeon RPG"
    CSS = """
    Screen {
        background: #0d0d14;
        color: #e8e6d8;
    }

    /* ---------- Main Menu ---------- */
    #menu-container {
        align: center middle;
        width: 100%;
        height: 100%;
    }
    #menu-title {
        content-align: center middle;
        color: #e0b52c;
        text-style: bold;
        width: 100%;
    }
    #menu-subtitle {
        content-align: center middle;
        color: #8f8c7a;
        width: 100%;
        margin-bottom: 1;
    }
    #menu-buttons {
        align: center middle;
        width: 40;
        height: auto;
        border: heavy #e0b52c;
        padding: 1 2;
    }
    #menu-buttons Button {
        width: 100%;
        margin-bottom: 1;
    }
    #menu-message {
        content-align: center middle;
        color: #d9534f;
        width: 100%;
        margin-top: 1;
    }

    /* ---------- Game Screen ---------- */
    #game-body {
        height: 1fr;
    }
    .panel {
        border: round #4a4a63;
        padding: 1 2;
        background: #14141f;
    }
    .map-panel {
        width: 3fr;
        color: #b7f27a;
        overflow: auto;
    }
    #side-panel {
        width: 1fr;
        min-width: 30;
    }
    .stats-panel {
        height: auto;
        color: #e8e6d8;
    }
    #legend-view {
        height: auto;
        color: #8f8c7a;
        margin-top: 1;
    }

    /* ---------- Combat Modal ---------- */
    #combat-container {
        align: center middle;
        width: 70;
        height: auto;
        border: heavy #d9534f;
        background: #14141f;
        padding: 1 2;
    }
    #combat-title {
        content-align: center middle;
        text-style: bold;
        color: #d9534f;
        width: 100%;
    }
    #combat-status {
        margin-top: 1;
        color: #e0b52c;
    }
    #combat-log {
        height: 9;
        margin-top: 1;
        color: #e8e6d8;
        border: round #4a4a63;
        padding: 0 1;
    }
    #combat-buttons {
        margin-top: 1;
        align: center middle;
    }
    #combat-buttons Button {
        margin-right: 1;
    }

    /* ---------- Inventory Modal ---------- */
    #inventory-container {
        align: center middle;
        width: 70;
        height: auto;
        border: heavy #5bc0de;
        background: #14141f;
        padding: 1 2;
    }
    #inventory-title {
        content-align: center middle;
        text-style: bold;
        color: #5bc0de;
        width: 100%;
    }
    #inventory-body {
        margin-top: 1;
        color: #e8e6d8;
    }
    #inventory-buttons {
        margin-top: 1;
        align: center middle;
    }
    #inventory-buttons Button {
        margin-right: 1;
    }

    /* ---------- Game Over ---------- */
    #gameover-container {
        align: center middle;
        width: 60;
        height: auto;
        border: heavy #d9534f;
        background: #14141f;
        padding: 2 3;
    }
    #gameover-title {
        content-align: center middle;
        text-style: bold;
        color: #d9534f;
        width: 100%;
    }
    #gameover-stats {
        content-align: center middle;
        width: 100%;
        margin-top: 1;
        color: #e0b52c;
    }
    #gameover-buttons {
        margin-top: 2;
        align: center middle;
    }
    #gameover-buttons Button {
        margin-right: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.state: GameState | None = None
        self.save_manager = SaveManager()

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


# =====================================================================
# ENTRY POINT
# =====================================================================

def main() -> None:
    app = DungeonRPGApp()
    app.run()


if __name__ == "__main__":
    main()
