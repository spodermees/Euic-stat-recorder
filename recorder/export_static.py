from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import DB_PATH, MY_POKEMON_PRESET

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "site"
OUTPUT_STATIC_DIR = OUTPUT_DIR / "static"


def fetch_rows(db: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    return db.execute(query, params).fetchall()


def export_site() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_STATIC_DIR.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    matches = fetch_rows(
        db,
        """
        SELECT id, name, created_at, format, winner, result, replay_url
        FROM matches
        ORDER BY id DESC
        """,
    )

    damage_stats = fetch_rows(
        db,
        """
        SELECT
            COUNT(*) AS total_hits,
            MIN(value_low) AS min_damage,
            MAX(value_high) AS max_damage,
            AVG((value_low + value_high) / 2.0) AS avg_damage
        FROM events
        WHERE event_type = 'damage' AND value_low IS NOT NULL AND value_high IS NOT NULL
        """,
    )[0]

    damage_rows = fetch_rows(
        db,
        """
        SELECT events.actor, events.target, events.move, events.value_low, events.value_high, matches.replay_url
        FROM events
        LEFT JOIN matches ON matches.id = events.match_id
        WHERE events.event_type = 'damage' AND events.value_low IS NOT NULL AND events.value_high IS NOT NULL
        """,
    )

    unique_names = sorted(
        {
            name
            for row in damage_rows
            for name in (row["actor"], row["target"])
            if name
        }
    )

    attacker_options = MY_POKEMON_PRESET
    opponent_options = [name for name in unique_names if name not in MY_POKEMON_PRESET]
    if not opponent_options:
        opponent_options = unique_names

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["tojson"] = lambda value: json.dumps(value, ensure_ascii=False)

    template = env.get_template("static_index.html")
    html = template.render(
        matches=matches,
        damage_stats=damage_stats,
        attacker_options=attacker_options,
        opponent_options=opponent_options,
        damage_rows=[dict(row) for row in damage_rows],
    )

    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(BASE_DIR / "static" / "style.css", OUTPUT_STATIC_DIR / "style.css")

    db.close()


if __name__ == "__main__":
    export_site()
