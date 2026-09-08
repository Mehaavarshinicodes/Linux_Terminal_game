"""Browser entrypoint for deploying Dungeon RPG to Vercel."""

from __future__ import annotations

import os
import random
from functools import wraps

from flask import Flask, jsonify, render_template_string, request, session

from main import Dungeon, Enemy, GameState

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-in-vercel")


INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dungeon RPG</title>
  <style>
    :root { --ink:#f4ead2; --muted:#a89b82; --gold:#f2c14e; --green:#9bd36a; --red:#e76f51; --panel:#171b23; --line:#354052; --bg:#0b0d12; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--ink); background:radial-gradient(circle at 18% 0%, #263b35 0, transparent 34%), radial-gradient(circle at 92% 100%, #35251d 0, transparent 32%), var(--bg); font-family:Georgia, 'Times New Roman', serif; }
    main { width:min(1120px, 100%); margin:auto; padding:30px 18px 46px; }
    header { display:flex; align-items:end; justify-content:space-between; gap:18px; border-bottom:1px solid var(--line); padding-bottom:18px; margin-bottom:22px; }
    h1 { margin:0; color:var(--gold); font-size:clamp(2rem, 6vw, 4.6rem); letter-spacing:.03em; line-height:.9; }
    .eyebrow { color:var(--green); text-transform:uppercase; letter-spacing:.2em; font:700 .72rem monospace; margin:0 0 10px; }
    .layout { display:grid; grid-template-columns:minmax(0, 1fr) 275px; gap:18px; }
    .panel { border:1px solid var(--line); background:rgba(23,27,35,.88); box-shadow:0 14px 40px #0005; }
    #map { overflow:auto; padding:18px; color:var(--green); font:clamp(.48rem, 1.4vw, .82rem)/1.25 'Courier New', monospace; white-space:pre; min-height:320px; }
    aside { display:flex; flex-direction:column; gap:14px; }
    .stats { padding:18px; }
    .stats h2 { margin:0 0 14px; font-size:1.1rem; color:var(--gold); }
    .stat { display:flex; justify-content:space-between; border-bottom:1px solid #ffffff12; padding:5px 0; font: .88rem monospace; }
    .stat span:last-child { color:var(--green); }
    .message { padding:15px 18px; color:#eadbb9; min-height:70px; font-size:1rem; line-height:1.4; }
    .controls { margin-top:18px; display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; max-width:390px; margin-left:auto; margin-right:auto; }
    button { border:1px solid #65758c; color:var(--ink); background:#222a36; padding:11px 9px; font:700 .78rem monospace; cursor:pointer; }
    button:hover { border-color:var(--gold); color:var(--gold); } button:active { transform:translateY(1px); }
    .wide { grid-column:span 3; } .danger { border-color:#914736; } .accent { border-color:#718f4f; }
    .modal { position:fixed; inset:0; display:grid; place-items:center; padding:18px; background:#0009; }
    .modal[hidden] { display:none; } .dialog { width:min(470px, 100%); padding:24px; }
    .dialog h2 { color:var(--red); margin-top:0; } .dialog p { line-height:1.5; }
    .dialog-actions { display:flex; gap:8px; flex-wrap:wrap; }
    @media (max-width:760px) { main { padding-top:20px; } header { display:block; } .layout { grid-template-columns:1fr; } aside { display:grid; grid-template-columns:1fr 1fr; } .message { grid-column:span 2; } #map { min-height:270px; } }
    @media (max-width:440px) { aside { display:flex; } }
  </style>
</head>
<body>
<main>
  <header><div><p class="eyebrow">A browser dungeon crawler</p><h1>DUNGEON RPG</h1></div><button id="new-game" class="accent">NEW GAME</button></header>
  <div class="layout">
    <section><div id="map" class="panel" aria-label="Dungeon map"></div><div id="controls" class="controls"><button data-action="up">UP</button><button data-action="inventory">INVENTORY</button><button data-action="save">SAVE</button><button data-action="left">LEFT</button><button data-action="down">DOWN</button><button data-action="right">RIGHT</button><button data-action="attack" class="danger">ATTACK</button><button data-action="potion" class="accent">POTION</button><button data-action="flee">FLEE</button></div></section>
    <aside><div id="stats" class="panel stats"></div><div id="message" class="panel message"></div></aside>
  </div>
</main>
<div id="game-over" class="modal" hidden><div class="dialog panel"><h2>YOU HAVE FALLEN</h2><p id="game-over-text"></p><button id="restart" class="accent">RESTART</button></div></div>
<script>
const $ = (id) => document.getElementById(id);
let state = null;
function stat(label, value) { return `<div class="stat"><span>${label}</span><span>${value}</span></div>`; }
function render() {
  if (!state) return;
  $('map').textContent = state.map;
  const p = state.player;
  $('stats').innerHTML = `<h2>HERO // LEVEL ${p.level}</h2>${stat('HP', `${p.hp}/${p.max_hp}`)}${stat('ATTACK', p.total_attack)}${stat('DEFENSE', p.total_defense)}${stat('XP', `${p.xp}/${p.xp_to_next}`)}${stat('GOLD', p.gold)}${stat('SCORE', p.score)}<h2 style="margin-top:20px">DUNGEON // ${state.level}</h2>${stat('ENEMIES', state.enemies)}${stat('TREASURE', state.treasure)}<h2 style="margin-top:20px">PACK</h2>${stat('POTIONS', p.inventory.potions)}${stat('SWORD', p.sword_equipped ? 'EQUIPPED' : p.inventory.swords)}${stat('SHIELD', p.shield_equipped ? 'EQUIPPED' : p.inventory.shields)}`;
  $('message').textContent = state.message;
  const combat = Boolean(state.combat);
  ['up','down','left','right','save','inventory'].forEach((name) => document.querySelector(`[data-action="${name}"]`).disabled = combat);
  ['attack','potion','flee'].forEach((name) => document.querySelector(`[data-action="${name}"]`).disabled = !combat);
  if (state.dead) { $('game-over-text').textContent = `Final score: ${p.score}. Dungeon level reached: ${state.level}.`; $('game-over').hidden = false; }
}
async function act(action) {
  const response = await fetch('/api/action', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action}) });
  state = await response.json(); render();
}
document.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => act(button.dataset.action)));
$('new-game').addEventListener('click', () => act('new'));
$('restart').addEventListener('click', () => { $('game-over').hidden = true; act('new'); });
document.addEventListener('keydown', (event) => { const keys = {ArrowUp:'up', w:'up', ArrowDown:'down', s:'down', ArrowLeft:'left', a:'left', ArrowRight:'right', d:'right', i:'inventory'}; if (keys[event.key]) { event.preventDefault(); act(keys[event.key]); } });
fetch('/api/state').then((response) => response.json()).then((data) => { state = data; render(); });
</script>
</body>
</html>
"""


def player_payload(player):
    data = player.to_dict()
    data["total_attack"] = player.total_attack
    data["total_defense"] = player.total_defense
    return data


def serialize(state, combat=None, dead=False):
    dungeon = state.dungeon
    return {
        "player": player_payload(state.player),
        "level": state.dungeon_level,
        "map": dungeon.render(state.player),
        "enemies": dungeon.remaining_enemies(),
        "treasure": len(dungeon.treasures),
        "message": state.message,
        "combat": combat,
        "dead": dead,
        "dungeon": {
            "grid": dungeon.grid,
            "start": dungeon.start,
            "exit": dungeon.exit,
            "enemies": [vars(enemy) for enemy in dungeon.enemies],
            "treasures": {f"{x},{y}": gold for (x, y), gold in dungeon.treasures.items()},
        },
    }


def restore(data):
    state = GameState()
    dungeon_data = data["dungeon"]
    state.dungeon_level = data["level"]
    state.player = state.player.from_dict(data["player"])
    dungeon = Dungeon.__new__(Dungeon)
    dungeon.level = state.dungeon_level
    dungeon.grid = dungeon_data["grid"]
    dungeon.height = len(dungeon.grid)
    dungeon.width = len(dungeon.grid[0])
    dungeon.start = tuple(dungeon_data["start"])
    dungeon.exit = tuple(dungeon_data["exit"])
    dungeon.rooms = []
    dungeon.treasures = {tuple(map(int, key.split(','))): gold for key, gold in dungeon_data["treasures"].items()}
    dungeon.enemies = []
    for raw in dungeon_data["enemies"]:
        enemy = Enemy(raw["name"], raw["max_hp"], raw["attack"], raw["defense"], raw["xp_reward"], raw["gold_reward"])
        enemy.hp, enemy.x, enemy.y = raw["hp"], raw["x"], raw["y"]
        dungeon.enemies.append(enemy)
    state.dungeon = dungeon
    state.player.x = data["player"].get("x", dungeon.start[0])
    state.player.y = data["player"].get("y", dungeon.start[1])
    state.message = data.get("message", "Explore the dungeon.")
    return state


def current_state():
    data = session.get("game")
    if not data:
        state = GameState()
        session["game"] = serialize(state)
        return state, None
    return restore(data), data.get("combat")


def save_state(state, combat=None, dead=False):
    session["game"] = serialize(state, combat, dead)
    session.modified = True


def api_route(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid game state"}), 400
    return wrapper


@app.get("/")
def index():
    return render_template_string(INDEX_HTML)


@app.get("/api/state")
def api_state():
    state, combat = current_state()
    save_state(state, combat)
    return jsonify(serialize(state, combat))


@app.post("/api/action")
@api_route
def api_action():
    action = request.get_json(silent=True).get("action")
    if action == "new":
        state, combat = GameState(), None
        save_state(state)
        return jsonify(serialize(state))

    state, combat = current_state()
    player, dungeon = state.player, state.dungeon
    if combat:
        enemy = dungeon.enemy_at(*combat)
        if enemy is None:
            combat = None
        elif action == "attack":
            damage = max(1, player.total_attack - enemy.defense + random.randint(-2, 2))
            enemy.hp -= damage
            state.message = f"You strike the {enemy.name} for {damage} damage."
            if enemy.hp <= 0:
                player.gold += enemy.gold_reward
                player.score += enemy.gold_reward * 2
                leveled = player.gain_xp(enemy.xp_reward)
                state.message = f"You defeated the {enemy.name}! +{enemy.xp_reward} XP, +{enemy.gold_reward} gold."
                if leveled:
                    state.message += f" Level up: {player.level}!"
                roll = random.random()
                if roll < .15: player.inventory["potions"] += 1
                elif roll < .22: player.inventory["swords"] += 1
                elif roll < .28: player.inventory["shields"] += 1
                combat = None
            else:
                _enemy_turn(state, enemy)
        elif action == "potion":
            healed = player.use_potion()
            if healed:
                state.message = f"You drink a potion and heal {healed} HP."
                _enemy_turn(state, enemy)
            else:
                state.message = "You have no potions left."
        elif action == "flee":
            if random.random() < .5:
                state.message = "You escape successfully."
                combat = None
            else:
                state.message = "Your escape fails."
                _enemy_turn(state, enemy)
        dead = not player.is_alive()
        if dead: state.message = "You have fallen in the dungeon."
        save_state(state, combat, dead)
        return jsonify(serialize(state, combat, dead))

    if action == "inventory":
        state.message = f"Inventory: {player.inventory['potions']} potions. Use the buttons below to manage combat."
    elif action == "save":
        state.message = "Your progress is held in this browser session."
    elif action in {"up", "down", "left", "right"}:
        directions = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        dx, dy = directions[action]
        nx, ny = player.x + dx, player.y + dy
        if dungeon.is_wall(nx, ny):
            state.message = "A wall blocks your path."
        else:
            enemy = dungeon.enemy_at(nx, ny)
            if enemy:
                combat = [nx, ny]
                state.message = f"A wild {enemy.name} blocks your path."
            else:
                player.x, player.y = nx, ny
                if (nx, ny) in dungeon.treasures:
                    gold = dungeon.treasures.pop((nx, ny))
                    player.gold += gold
                    player.score += gold
                    state.message = f"You found {gold} gold."
                if (nx, ny) == dungeon.exit:
                    state.next_level()
                    state.message = f"You descend to dungeon level {state.dungeon_level}!"
    save_state(state, combat)
    return jsonify(serialize(state, combat))


def _enemy_turn(state, enemy):
    player = state.player
    damage = max(1, enemy.attack - player.total_defense + random.randint(-2, 2))
    player.take_damage(damage)
    state.message += f" {enemy.name} hits you for {damage}."


if __name__ == "__main__":
    app.run(debug=True)
