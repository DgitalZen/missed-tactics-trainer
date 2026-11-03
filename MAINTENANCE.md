# Maintenance guide

How to keep the project working, update its parts, change it safely, and publish new versions.
Read `HOW_IT_WORKS.md` first for the structure and data formats.

## Golden rules

1. **Never break people's data.** Users have a library (`puzzles.json`), a sync record (`sync.json`), and training
   progress in their browser. Any change must keep old data working, or ship a migration.
2. **Never rename browser storage keys** (`mtp1`, `mtp1log`, `mtp1eng`) without a migration that reads the old key.
3. **Add, don't change.** New puzzle fields and progress fields should be optional, so older data still loads.
4. **Test by hand before every release** (checklist below). There are no automated tests yet.
5. **Keep personal data out of the repository.** Check `git status` or the GitHub upload list for `puzzles.json`,
   `sync.json`, `games/`, exports, and PGNs before every commit. History is permanent in a public repository.

## Routine checks (every few months)

| Check | What to do |
|---|---|
| Does it still run? | Follow the sample-run checklist below on a clean copy |
| python-chess | `python -m pip install --upgrade chess`, then rerun the checklist |
| Stockfish | Download the newest release, replace the one in the `stockfish` folder, rerun the checklist |
| Lichess import | Run `--lichess YOURNAME --max 3` and confirm games download and analyse |
| Documentation | Make sure `COMMANDS.md` lists every option in `pgn_puzzles.py --help` |

## Updating each dependency

### python-chess (Python library)

The code uses: reading PGNs, `Board`, move generation and SAN, `engine.analyse` with `multipv`, score objects
(`pov`, `score`, `mate`), `Board.attacks`, `attackers`, `pin`, `is_pinned`, `between`, `checkers`.
After upgrading, run the checklist, then `--retag` on a library and check the tags still look right.
If something breaks, the error will name the function; check python-chess's release notes for it.
The license is GPL-3.0-or-later, which is why this project uses a GPL-compatible license.

### Stockfish

Any UCI-compatible engine works. Newer Stockfish versions may change evaluation scale slightly, so tag thresholds
(`--blunder`, `--mistake`) behave a little differently. That is expected. Stockfish is not bundled; users download it.

### chess.js (inside `assets.json`)

The page expects chess.js version 1 behaviour: `new Chess(fen)`, `moves({square, verbose})`, `move()` (throws on
illegal moves), `undo()`, `history({verbose})`, `fen()`, `turn()`, `isGameOver()`, `isCheckmate()`.
A new major version may rename these. To rebuild `assets.json` with a newer chess.js (needs Node.js and internet):

```python
# run in an empty folder, after:  npm pack chess.js   and unpacking the .tgz so "package/" exists
import json, base64, glob, os
cjs = open("package/dist/cjs/chess.js", encoding="utf-8").read()
pieces = {}
for f in sorted(glob.glob("pieces/*.svg")):          # wK wQ wR wB wN wP bK bQ bR bB bN bP
    data = open(f, "rb").read()
    pieces[os.path.basename(f)[:-4]] = "data:image/svg+xml;base64," + base64.b64encode(data).decode()
json.dump({"chessjs": cjs, "pieces": pieces}, open("assets.json", "w"))
```

The piece images come from the Lichess repository's `cburnett` set. Keep `THIRD_PARTY.md` accurate if either source changes.
Then rebuild the page (`--rebuild`) and run the checklist, including dragging and stepping through moves.

### Lichess API

The importer uses `GET /api/games/user/{username}` with `max`, `perfType`, `since`, `sort`, and the PGN content type.
If Lichess changes parameters or rate limits, the symptoms are import errors or empty downloads. See Lichess's API
documentation. The tool already waits and retries on HTTP 429.

## Common changes

### Add a new pattern tag

1. In `pgn_puzzles.py`, add detection: for a mate pattern, extend `mate_patterns`; for a tactic, extend
   `first_move_themes`. Return a short lowercase name (for example `"deflection"`).
2. In `trainer_template.html`, add the label to the `TL` object so it displays nicely and appears in the filter.
3. Run `python pgn_puzzles.py --retag` on a test library and inspect puzzles that should and should not get the tag.
   Rule-based detection produces false positives, so test positions where the tag is wrong as well as right.
4. Document it in `HOW_IT_WORKS.md` and `CHANGELOG.md`.

### Add a new analysis option

1. Add `ap.add_argument(...)` in `main()` and use it where needed.
2. Add it to `COMMANDS.md` with its default.
3. If it changes how puzzles are chosen, existing puzzles will not change; mention that in the docs.

### Add a field to puzzles

1. Write it where the puzzle dictionary is built in `process_game`.
2. Make the page tolerate it being missing (`p.field || default`), because old libraries will not have it.
3. If it can be computed from existing data, add a `--retag`-style option so users can update old puzzles.
4. Document it in the format table in `HOW_IT_WORKS.md`.

### Add a new tag or setting in the trainer

- "Why did I miss it?" tags live in the `TAGS` list near the top of the script in `trainer_template.html`.
  Changing or removing a tag does not delete tags users already saved.
- Anything stored per puzzle goes inside the `mtp1` record. Anything stored per attempt goes in the log entry,
  and the import code (`mergeLog`) must copy any new field, or it will be dropped on import.

### Change the export format

Bump `version` in `exportProgress`, keep reading the older versions in `importProgress`, and note it in
`CHANGELOG.md`. Never make a new version unable to read an old export.

## Testing checklist (by hand)

Use a clean folder with the files from the repository and a Stockfish in the `stockfish` folder.

1. `python pgn_puzzles.py examples/sample.pgn --player "SamplePlayer" --no-open`
   Expect two games analysed and several puzzles, including missed mates (the first game misses `Qxf7#`).
2. Run it again. Expect "already analysed (skipped)" and no new puzzles.
3. `python pgn_puzzles.py --retag` completes and reports tags.
4. `python pgn_puzzles.py --serve`, then open `http://localhost:8765/` and check:
   - the board is square and all rows are the same height
   - the filter dropdowns all show and work, including the colour and pattern filters
   - "Is there a tactic?" appears; answering both ways works
   - a wrong move gives a second try; a correct one starts the line; the opponent replies
   - Hint shows the piece, then the square; Show solution works; Try again is unscored
   - arrow keys step through the moves; Enter goes to the next puzzle
   - engine arrows appear after finishing, with plus meaning good for White
   - the timer counts down and a timeout logs as a miss
   - the Stats tab opens and its numbers change after more attempts
5. Export progress, clear the site's data (or use a second browser), and import the file. Progress, notes, and
   history should come back, and importing the same file twice should add nothing.
6. With a real Lichess username: `--lichess NAME --max 3 --no-open` downloads, analyses, and a second run reports nothing new.
7. Press Ctrl+C in the middle of an import and confirm the library is still valid and the next run continues.
8. Test on the oldest Python version you claim to support, and on Windows and Mac or Linux if you can.

## Releasing a new version

1. Update `CHANGELOG.md` with what changed, including anything users must do.
2. Update the version in the User-Agent string (`USER_AGENT` in `pgn_puzzles.py`).
3. Update any docs affected by changes.
4. Run the testing checklist.
5. On GitHub: upload or commit the files, then **Releases > Create a new release** with a tag like `v0.2.0`
   and the changelog text as the description.
6. Tell existing users to replace the program files and keep their `puzzles.json`, `sync.json`, `games/`, and
   exported progress.

## Troubleshooting for maintainers

| Symptom | Likely cause |
|---|---|
| Page shows no pieces or the board does not respond | `assets.json` missing or malformed; rebuild the page after fixing it |
| Page works as a file but not on localhost (or the reverse), and progress is "gone" | Browser storage is per address; use export and import |
| Distorted board rows | A style rule is overriding the board grid; check the CSS for classes reused with different meanings |
| Arrows missing | The server isn't running (`--serve`), or the "Engine arrows" box is unticked |
| Evaluations look reversed | The sign convention: arrows use White's point of view, stored `best_eval` uses the mover's |
| Tags look wrong after a change | Run `--retag`; check the pattern rules in `HOW_IT_WORKS.md` |
| Import re-analyses games it should skip | `sync.json` was deleted or `--fresh`/`--reanalyse` was used |
| Library seems lost | Check `puzzles.backup.json`; rename it to `puzzles.json` to restore the previous version |

## Ideas not built yet

- Chess.com import (monthly archives; one request at a time, with a User-Agent)
- Longer stored engine lines, so longer mates can be played out and tagged
- Tactic detection beyond the first move, pins against pieces other than the king, hook and Boden's mates
- Touch buttons for stepping through moves, and a choice of promotion piece
- Move animation, sounds, themes and board colours
- A split of statistics by colour
- Automated tests, starting with the pattern detection
