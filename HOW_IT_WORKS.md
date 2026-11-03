# How it works

This document explains the parts of the project, how data moves through them, and the formats that
connect them. It is written for people who want to understand or change the code. If you only want to use the
tool, read `GETTING_STARTED.md` and `COMMANDS.md` instead.

## The big picture

```
 PGN file or Lichess  -->  pgn_puzzles.py  -->  puzzles.json  -->  puzzles.html  -->  your browser
   (your games)            (Stockfish finds       (the library)     (built from        (trainer; results
                            your mistakes)                           trainer_template   stay in the browser)
                                                                     + assets.json)
```

There are two separate halves:

1. **Analysis (Python, slow, runs once per game).** Reads games, asks Stockfish about every move, and writes puzzles
   into `puzzles.json`.
2. **Trainer (HTML and JavaScript, instant).** A single page built from the library. It never runs the analysis
   itself, so you can change the page and rebuild in seconds.

The only live link between them is the optional `--serve` mode, where the page asks the local Python server for
Stockfish's opinion of the position on the board (the arrows).

## The files

| File | Role | Edit when |
|---|---|---|
| `pgn_puzzles.py` | Everything on the Python side: analysis, library, Lichess import, pattern detection, local server | Changing how puzzles are found, tagged, or imported |
| `trainer_template.html` | The whole trainer page: board, line play, filters, stats, progress | Changing how the page looks or behaves |
| `assets.json` | Bundled chess rules (chess.js) and piece images, inserted into the page so it works offline | Updating chess.js or the piece set (see `MAINTENANCE.md`) |
| `requirements.txt` | Python dependency (`chess`) | Adding a Python dependency |
| `examples/sample.pgn` | Two tiny games for trying the tool | Rarely |
| `README.md`, `GETTING_STARTED.md`, `COMMANDS.md`, `THIRD_PARTY.md`, `CHANGELOG.md` | Documentation | When behaviour or options change |

Files created at run time (never committed; see `.gitignore`):

| File | What it holds |
|---|---|
| `puzzles.json` | The puzzle library. Merged into on every run, never overwritten unless `--fresh` is used. |
| `puzzles.backup.json` | The library as it was before the last save |
| `puzzles.html` | The generated trainer page (`trainer_template.html` plus the library plus `assets.json`) |
| `sync.json` | Which games were analysed, and where each Lichess import stopped |
| `games/` | PGN files downloaded from Lichess |
| `settings.json` | Optional. `{"engine": "path"}` if Stockfish is not found automatically |

## Inside `pgn_puzzles.py`

### Analysis (`process_game`)

For each game, and for each move by the player (or both sides if no `--player` was given):

1. Skip the first `--skip-plies` half-moves (opening book). Skip variants other than standard chess.
2. Ask Stockfish about the position **before** the move (`--depth`, `--multipv` lines). Evaluations are clamped to
   plus or minus 1000 centipawns so a mate and a huge advantage count the same.
3. Build the **accept set**: every move within `--tolerance` centipawns of the best. When the best line is a mate,
   only moves that mate as fast count, so a slower mate is never accepted.
4. If the move played is in the accept set, it was fine. It may be remembered as a candidate **quiet position**
   (roughly level evaluation, not in check, no clearly sole best move).
5. Otherwise, analyse the position after the move and compute the **loss** (best evaluation minus resulting
   evaluation). Then classify:

| Category | Rule |
|---|---|
| `missed_mate` | A forced mate existed and the move played gave it up |
| `long_route` | A mate existed, and the move played still mates but at least two moves slower |
| `missed_win` | Loss at least `--blunder`, the best move gave at least +3, and the player still isn't clearly worse |
| `blunder` | Loss at least `--blunder` (250 by default) |
| `mistake` | Loss at least `--mistake` (120 by default) |
| `none` | A quiet position: nothing forced, used for the "is there a tactic?" step |

6. Positions where the player was already clearly lost (below -500) are skipped, since blunders there make poor puzzles.
7. Each puzzle gets an `id` (a short hash of position plus best move) and its pattern `themes`.

### The puzzle format (`puzzles.json` is a list of these)

| Field | Meaning |
|---|---|
| `id` | 10-character hash of `fen` + `best`. Used to remove duplicates and to attach progress. |
| `fen` | Position before the player's move |
| `turn` | `"white"` or `"black"`: the side to move, which is the player |
| `move_no` | Full-move number in the game |
| `game` | `{white, black, date, site}` from the PGN headers |
| `category` | One of the categories above |
| `best` | Best move in UCI form (`e2e4`) |
| `best_san` | Best move in standard notation |
| `accept` | List of UCI moves that count as correct |
| `played_san` | The move actually played |
| `loss` | Evaluation drop in centipawns (0 for quiet positions) |
| `best_eval` | Evaluation of the best move from the **mover's** point of view, as text (`+1.8`, `#3`) |
| `pv` | The engine's line from the position as standard notation, at most six half-moves (three for quiet positions) |
| `themes` | List of pattern tags (see below) |

New optional fields can be added without breaking old libraries, because the page treats missing fields as empty.

### Pattern detection (`tag_puzzle`, `mate_patterns`, `first_move_themes`)

Rule-based, using python-chess. It replays `pv` from `fen`.

- **Mate patterns** are judged on the final position when the line ends in checkmate: back-rank, smothered, Arabian,
  Anastasia's, double-bishop. Any puzzle whose best evaluation is a mate also gets `mate`.
- **Tactics** are judged on the player's **first move only**: `fork`, `pin` (absolute pins), `skewer`,
  `discovered_attack`, `hanging_piece`.
- Quiet positions get no tags.

Because the stored line holds at most six half-moves, mate patterns are only found for mates in 1 to 3.
`--retag` recomputes `themes` for the whole library without touching anything else.

### Library and sync

- `load_library` / `save_library`: the library is merged, never replaced. Before each save the old file is copied
  to `puzzles.backup.json`. If `puzzles.json` is unreadable the program stops instead of overwriting it.
- `sync.json` holds `analysed` (game identities) and `lichess` (per-user last-game timestamp).
  A game's identity is its `Site` URL when it has one, otherwise a hash of its headers and length.
  Puzzles also remember their game's URL, so older runs are recognised as analysed.
- Runs can be interrupted with Ctrl+C: what was analysed so far is merged and saved, and the Lichess timestamp is only
  advanced after a complete run.

### Lichess import (`download_lichess`)

Calls `/api/games/user/{username}` with `max`, `perfType`, and optionally `since` (with `sort=dateAsc`, so a later
run continues where the last one stopped). One request at a time, identifies itself with a User-Agent, waits and
retries on HTTP 429, and reports clear errors for unknown users or bad tokens. The PGN is saved under `games/`, then
analysed like any other file with exact username matching.

### Building the page (`build_page`)

`trainer_template.html` contains three placeholders, replaced in this order:

| Placeholder | Replaced with |
|---|---|
| `__DATA__` | The library as JSON (`</` is escaped so it cannot close the script tag) |
| `__PIECES__` | The piece images from `assets.json` (data URIs) |
| `__CHESSJS__` | The chess.js code from `assets.json`, wrapped so it works as a plain script |

`--rebuild` does this step alone. `--serve` does it, then starts the server.

### The local server (`serve`)

Python's built-in HTTP server on `127.0.0.1` only (not reachable from other computers):

| Route | Returns |
|---|---|
| `/` or `/puzzles.html` | The generated page |
| `/ping` | `ok`. The page uses it to detect that the server is running |
| `/analyse?fen=...` | The top three moves for that position as JSON: `from`, `to`, `san`, `eval` (from **White's** point of view) |

One Stockfish process is kept running and shared, with requests taking turns (`--think` seconds each).

## Inside `trainer_template.html`

One file with its styles and script. It has no build step and no external requests (except to the local server).

### Puzzle flow (states)

`detect` (is there a tactic?) leads to `solve` (find the move) or straight to `done`. A correct first move can lead to
`line` (playing out the engine's line). `done` allows free exploration, stepping with the arrow keys, and **Try again**
(unscored). The first answer to each puzzle is scored and logged; practice tries and exploration are not.

### Progress and history (all in the browser)

| Storage key | Contents |
|---|---|
| `mtp1` | Per-puzzle progress: `{box, due, upd, tags, note}`. `box` is the spaced-repetition level, `due` the next review time (ms), `upd` the last change (ms). |
| `mtp1log` | Attempt history, one entry per scored attempt (below) |
| `mtp1eng` | Whether engine arrows are switched on |

Spaced repetition: correct raises the box (intervals 0, 1, 3, 7, 21, 60 days), wrong resets it to 0.

Attempt log entry: `{t, id, c, ok, tr, d, dms, ms, to}`: time, puzzle id, category, correct (1/0), wrong tries before
finishing, the yes/no answer to "is there a tactic?" (`"y"`/`"n"`), milliseconds to answer that, total milliseconds,
and 1 if the timer ran out.

Browser storage belongs to one address. The page at `http://localhost:8765/` and a `puzzles.html` opened as a plain
file have **separate** storage. That is why the export and import buttons exist.

### Export file (version 2)

```json
{"app": "missed-tactics", "version": 2, "exported": "ISO date", "progress": {...}, "log": [...]}
```

Import merges rather than replaces: a progress record with a newer `upd` wins (and keeps local tags and notes if the
incoming one has none), and log entries are added unless an entry with the same time and puzzle id already exists.
A version 1 file (just the progress object) is also accepted.

### Evaluation sign convention

Arrows show evaluations from **White's** point of view (plus is good for White). The `best_eval` stored on each puzzle
is from the mover's side; the page converts it to White's point of view for display (`whiteEval`).

### Main areas of the script

| Area | Functions |
|---|---|
| Progress, log, export and import | `save`, `saveLog`, `exportProgress`, `mergeProgress`, `mergeLog`, `importProgress` |
| Filters and queue | `buildFilter`, `start`, `inRange`, `opp` |
| Timer | `startTimer`, `stopTimer` |
| Puzzle flow | `next`, `answer`, `finish`, `showDetail`, `endLine`, `retry`, `record`, `logAttempt` |
| Board and moves | `render`, `click`, `attempt`, `play`, `reply`, `refresh`, `stepBack`, `stepFwd`, `hintStep` |
| Engine arrows | `eng`, `drawArrows` |
| Notes and tags | `buildWhy`, `toggleTag`, `setNote` |
| Stats | `renderStats`, `table`, `group`, `showTab` |

## Known technical limits

- Engine lines are capped at six half-moves, which limits line play and mate-pattern detection.
- Tactic tags use only the first move and simple rules, so mislabels happen.
- There are no automated tests yet. `MAINTENANCE.md` lists what to check by hand.
- Chess.com import does not exist yet.
