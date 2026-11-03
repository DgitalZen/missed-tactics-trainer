# Command reference

Every command starts with `python pgn_puzzles.py`. Run them from the project folder, or give full paths.
Examples use `YourLichessName` and `"YourName"` as placeholders; replace them with your own.

## Quick routine

| When | Command |
|---|---|
| Practising | `python pgn_puzzles.py --serve` |
| After playing new Lichess games | `python pgn_puzzles.py --lichess YourLichessName --no-open`, then `--serve` |
| Games from another source (PGN file) | `python pgn_puzzles.py my_games.pgn --player "YourName" --no-open`, then `--serve` |
| Pattern tags look wrong | `python pgn_puzzles.py --retag` |
| Something looks wrong with the library | Check `puzzles.backup.json`, then see Troubleshooting |

## Training

### `--serve`
Rebuilds the trainer page from your library, starts Stockfish, and opens `http://localhost:8765/`.
Leave the window open while you train; press Ctrl+C to stop.

| Option | Meaning | Default |
|---|---|---|
| `--port N` | Port to use. Your progress is stored per address, so keep it the same. If you change it, export and re-import your progress once. | 8765 |
| `--think SECONDS` | Engine thinking time per position for the arrows | 0.8 |
| `--no-open` | Don't open the browser automatically | off |

## Importing games

### `--lichess USERNAME`
Downloads games from Lichess, analyses the ones not seen before, and adds the puzzles to your library.
The username is matched exactly. Games already analysed are remembered in `sync.json` and skipped next time.
The first run takes the latest games; later runs continue from where the previous one stopped.

| Option | Meaning | Default |
|---|---|---|
| `--max N` | Most games to download per run | 100 |
| `--since YYYY-MM-DD` | Only games from this date on | last sync point |
| `--perf TYPES` | Game types, comma separated (`rapid,classical`, `blitz,rapid`, or `all`) | `rapid,classical` |
| `--token TOKEN` | Optional Lichess API token for private games (or set `LICHESS_TOKEN`) | none |

Good to know:
- Variants such as Chess960 and Antichess are skipped.
- Press Ctrl+C at any time; what has been analysed so far is saved.
- Large imports take a long time. Start small (for example `--max 5`) the first time.

### `FILE.pgn --player "NAME"`
Analyses any PGN file (one game or many) from any source. You can pass several files and repeat `--player`
for several accounts. The name is matched as a case-insensitive part of the White/Black name.
Without `--player`, both sides of every game are analysed.

## Maintenance

### `--rebuild`
Regenerates `puzzles.html` from the library without analysing anything or starting Stockfish.
You rarely need it, because `--serve` already rebuilds. Use it to open the page as a plain file.

### `--retag`
Re-detects tactic and mate patterns (fork, pin, skewer, back-rank, and so on) on every puzzle,
saves the library, and rebuilds the page. Use it after the pattern rules are improved.
It does not touch your progress.

## Analysis settings (add to an import)

The defaults are sensible. Change them only for a reason.

| Option | Meaning | Default |
|---|---|---|
| `--depth N` | Engine depth. Higher is stronger and slower; 12 is a quick pass | 14 |
| `--threads N` | Engine threads; use up to your core count, leaving a couple free | 2 |
| `--multipv N` | Candidate lines checked, used to accept equally good alternatives | 3 |
| `--skip-plies N` | Ignore the first N half-moves (opening book); 0 includes the opening | 8 |
| `--decoys N` | Quiet "nothing here" positions to add per game; 0 turns them off | 1 |
| `--blunder N` | Evaluation drop (centipawns) counted as a blunder or missed win | 250 |
| `--mistake N` | Evaluation drop counted as a mistake | 120 |
| `--tolerance N` | How close to the best move an alternative can be and still count as correct | 30 |
| `--engine PATH` | Use a specific Stockfish executable | found automatically |

## Housekeeping

| Option | Meaning |
|---|---|
| `--reanalyse` | Analyse games even if they were analysed before (for example after raising `--depth`). Adds no duplicates. |
| `--out-dir FOLDER` | Keep the library somewhere other than next to the script |
| `--seed N` | Changes which quiet positions are picked |
| `--fresh` | **Ignores the existing library and sync record and starts new.** The previous library is copied to `puzzles.backup.json`, but only until the next save. Use only when you really want to start over. |
| `--no-open` | Don't open the browser when the run finishes |

## Files the tool creates

| File | What it is |
|---|---|
| `puzzles.json` | Your puzzle library. Back this up. |
| `puzzles.html` | The trainer page, rebuilt from the library |
| `puzzles.backup.json` | The library as it was before the last save |
| `sync.json` | Which games have been analysed and where each Lichess import stopped |
| `games/` | PGN files downloaded from Lichess |
| `settings.json` | Optional. Only needed to point to Stockfish if it is not found automatically |

Your training progress, notes, tags, and attempt history live in the browser, not in these files.
Use **Export progress** on the page to save them, and **Import progress** to restore them.

## Troubleshooting

- **"Stockfish not found":** unzip Stockfish into a folder called `stockfish` next to the script, or pass `--engine "PATH"`, or create a `settings.json` containing `{"engine": "FULL PATH"}`.
- **"Can't find the PGN file":** check the name and folder. The message lists the `.pgn` files it can see.
- **"Can't find trainer_template.html" or `assets.json`:** these must sit in the same folder as the script.
- **The page looks unchanged after an update:** press Ctrl+F5 to clear the browser's cached copy.
- **Port busy:** another copy is still running. Close it, or use `--port`.
- **Progress seems missing:** check you are opening the same address (`http://localhost:8765/`). Import your latest progress export.
- **Lichess says "slow down":** the tool waits and retries automatically.
