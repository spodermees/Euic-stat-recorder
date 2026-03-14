from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import DB_PATH, MY_POKEMON_PRESET, PREP_SECTIONS

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR.parent / "docs"
OUTPUT_STATIC_DIR = OUTPUT_DIR / "static"

RAW_RATING_PATTERN = re.compile(
    r"^\|raw\|\s*(?P<user>.+?)'s rating:\s*(?P<before>\d+).*?<strong>(?P<after>\d+)</strong>",
    re.IGNORECASE,
)


def fetch_rows(db: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    return db.execute(query, params).fetchall()


def fetch_row(db: sqlite3.Connection, query: str, params: tuple = ()) -> sqlite3.Row | None:
    return db.execute(query, params).fetchone()


def _active_team(db: sqlite3.Connection) -> sqlite3.Row | None:
    return fetch_row(
        db,
        """
        SELECT id, name, updated_at
        FROM prep_teams
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
    )


def export_site() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_STATIC_DIR.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    active_team = _active_team(db)
    active_team_id = active_team["id"] if active_team else None

    teams = fetch_rows(
        db,
        """
        SELECT id, name, updated_at
        FROM prep_teams
        ORDER BY updated_at DESC, id DESC
        """,
    )

    team_pokemon = []
    if active_team_id is not None:
        team_pokemon = fetch_rows(
            db,
            """
            SELECT nickname, species, source_url, created_at
            FROM team_pokemon
            WHERE team_id = ?
            ORDER BY id DESC
            """,
            (active_team_id,),
        )

    if active_team_id is None:
        matches = fetch_rows(
            db,
            """
            SELECT id, name, created_at, format, player1, player2, winner, result, replay_url, rating_user, rating_after
            FROM matches
            ORDER BY id DESC
            """,
        )
    else:
        matches = fetch_rows(
            db,
            """
            SELECT id, name, created_at, format, player1, player2, winner, result, replay_url, rating_user, rating_after
            FROM matches
            WHERE team_id = ?
            ORDER BY id DESC
            """,
            (active_team_id,),
        )

    if active_team_id is None:
        totals = fetch_rows(
            db,
            """
            SELECT COUNT(*) AS total_events
            FROM events
            """,
        )[0]
    else:
        totals = fetch_rows(
            db,
            """
            SELECT COUNT(*) AS total_events
            FROM events
            INNER JOIN matches ON matches.id = events.match_id
            WHERE matches.team_id = ?
            """,
            (active_team_id,),
        )[0]

    if active_team_id is None:
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
    else:
        damage_stats = fetch_rows(
            db,
            """
            SELECT
                COUNT(*) AS total_hits,
                MIN(events.value_low) AS min_damage,
                MAX(events.value_high) AS max_damage,
                AVG((events.value_low + events.value_high) / 2.0) AS avg_damage
            FROM events
            INNER JOIN matches ON matches.id = events.match_id
            WHERE matches.team_id = ?
              AND events.event_type = 'damage'
              AND events.value_low IS NOT NULL
              AND events.value_high IS NOT NULL
            """,
            (active_team_id,),
        )[0]

    if active_team_id is None:
        damage_rows = fetch_rows(
            db,
            """
            SELECT events.actor, events.target, events.move, events.value_low, events.value_high, matches.replay_url
            FROM events
            LEFT JOIN matches ON matches.id = events.match_id
            WHERE events.event_type = 'damage' AND events.value_low IS NOT NULL AND events.value_high IS NOT NULL
            """,
        )
    else:
        damage_rows = fetch_rows(
            db,
            """
            SELECT events.actor, events.target, events.move, events.value_low, events.value_high, matches.replay_url
            FROM events
            INNER JOIN matches ON matches.id = events.match_id
            WHERE matches.team_id = ?
              AND events.event_type = 'damage'
              AND events.value_low IS NOT NULL
              AND events.value_high IS NOT NULL
            """,
            (active_team_id,),
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

    prep_notes_rows = fetch_rows(
        db,
        """
        SELECT section, content
        FROM prep_notes
        """,
    )
    prep_notes = {row["section"]: row["content"] or "" for row in prep_notes_rows}

    if active_team_id is None:
        prep_matchup_rows = fetch_rows(
            db,
            """
            SELECT id, title, updated_at
            FROM prep_matchups
            ORDER BY updated_at DESC, id DESC
            """,
        )
    else:
        prep_matchup_rows = fetch_rows(
            db,
            """
            SELECT id, title, updated_at
            FROM prep_matchups
            WHERE team_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (active_team_id,),
        )
    prep_matchups = []
    for matchup in prep_matchup_rows:
        notes_rows = fetch_rows(
            db,
            """
            SELECT section, content
            FROM prep_matchup_notes
            WHERE matchup_id = ?
            """,
            (matchup["id"],),
        )
        prep_matchups.append(
            {
                **dict(matchup),
                "notes": {row["section"]: row["content"] or "" for row in notes_rows},
            }
        )

    match_logs: dict[int, list[dict]] = {}
    if matches:
        match_ids = [int(row["id"]) for row in matches]
        placeholders = ",".join("?" for _ in match_ids)
        log_rows = fetch_rows(
            db,
            f"""
            SELECT match_id, turn, raw_line
            FROM log_lines
            WHERE match_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(match_ids),
        )
        for row in log_rows:
            match_logs.setdefault(int(row["match_id"]), []).append(
                {"turn": row["turn"], "raw_line": row["raw_line"]}
            )

    rating_history = []
    if active_team_id is None:
        rating_rows = fetch_rows(
            db,
            """
            SELECT rating_user, rating_after, format, created_at
            FROM matches
            WHERE rating_user IS NOT NULL AND rating_after IS NOT NULL
            ORDER BY id ASC
            LIMIT 500
            """,
        )
    else:
        rating_rows = fetch_rows(
            db,
            """
            SELECT rating_user, rating_after, format, created_at
            FROM matches
            WHERE rating_user IS NOT NULL AND rating_after IS NOT NULL
              AND team_id = ?
            ORDER BY id ASC
            LIMIT 500
            """,
            (active_team_id,),
        )
    for row in rating_rows:
        rating_history.append(
            {
                "user": row["rating_user"],
                "elo": int(row["rating_after"]),
                "format": row["format"],
                "created_at": row["created_at"],
            }
        )

    if not rating_history:
        if active_team_id is None:
            raw_rows = fetch_rows(
                db,
                """
                SELECT log_lines.raw_line, log_lines.created_at, matches.format
                FROM log_lines
                LEFT JOIN matches ON matches.id = log_lines.match_id
                WHERE log_lines.raw_line LIKE '%rating:%'
                ORDER BY log_lines.id ASC
                LIMIT 800
                """,
            )
        else:
            raw_rows = fetch_rows(
                db,
                """
                SELECT log_lines.raw_line, log_lines.created_at, matches.format
                FROM log_lines
                LEFT JOIN matches ON matches.id = log_lines.match_id
                WHERE log_lines.raw_line LIKE '%rating:%'
                  AND matches.team_id = ?
                ORDER BY log_lines.id ASC
                LIMIT 800
                """,
                (active_team_id,),
            )
        for row in raw_rows:
            rating_match = RAW_RATING_PATTERN.match(row["raw_line"] or "")
            if not rating_match:
                continue
            rating_history.append(
                {
                    "user": rating_match.group("user").strip(),
                    "elo": int(rating_match.group("after")),
                    "format": row["format"],
                    "created_at": row["created_at"],
                }
            )

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["tojson"] = lambda value: json.dumps(value, ensure_ascii=False)

    template = env.get_template("static_index.html")

    def render_page(output_path: Path, static_prefix: str) -> None:
        html = template.render(
            matches=matches,
            totals=totals,
            damage_stats=damage_stats,
            attacker_options=attacker_options,
            opponent_options=opponent_options,
            damage_rows=[dict(row) for row in damage_rows],
            rating_history=rating_history,
            teams=[dict(row) for row in teams],
            active_team=dict(active_team) if active_team else None,
            team_pokemon=[dict(row) for row in team_pokemon],
            match_logs=match_logs,
            prep_sections=PREP_SECTIONS,
            prep_notes=prep_notes,
            prep_matchups=prep_matchups,
            static_prefix=static_prefix,
        )
        output_path.write_text(html, encoding="utf-8")

    render_page(OUTPUT_DIR / "index.html", "static")
    render_page(BASE_DIR.parent / "index_website.html", "docs/static")
    shutil.copytree(BASE_DIR / "static", OUTPUT_STATIC_DIR, dirs_exist_ok=True)

    db.close()


if __name__ == "__main__":
    export_site()
