I want a code that records my showdown matches by keeping track of the chat to collect data like items and dmg ranges en being able to look quickly at the data

## Showdown Recorder Dashboard

This folder now includes a small web dashboard with a local SQLite database. The UI is read-only: you can only add data by uploading a log file or calling the API.

### How to run

1) Install dependencies

```
pip install -r requirements.txt
```

2) Start the server

```
python app.py
```

3) Open the dashboard at:

http://127.0.0.1:5000

### Add data

- Upload a Showdown chat log as a .txt file in the dashboard.
- Or POST JSON to /api/ingest with field:

```
{
	"log": "<paste full chat log here>"
}
```

### What is extracted

- Items (basic triggers like "X's Leftovers restored")
- Damage lines (single % or a range)

The raw line is always stored so you can review what was captured.

### Owner detection (my Pokémon vs opponent)

On the match page, enter your nicknames and the opponent nicknames (comma or line separated). The table will label events as Mine/Opponent/Unknown based on those names and common keywords like "opposing".

### Live watcher (keeps log every turn)

1) Start the Flask app
2) Run the watcher

```
python watcher.py
```

By default it watches recorder/live_log.txt. If you want another file, set:

- SHOWDOWN_LOG_PATH
- SHOWDOWN_API_URL (optional)

For the desktop app, you can point the watcher to a folder and it will follow the newest .txt log automatically:

- SHOWDOWN_LOG_DIR

### Auto-stream from the browser (no log file)

If you want it to work automatically while you play:

1) Install Tampermonkey in your browser.
2) Create a new userscript and paste the contents of showdown_user_script.js.
3) Start the Flask app.
4) Open a battle on Showdown. The log is streamed to /api/ingest_line automatically.

### Replay URL import (after battle)

Paste a battle replay URL on the homepage and it will fetch the replay log and import it.