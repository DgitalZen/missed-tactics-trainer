# Missed Tactics Trainer

Train on the positions that don't tell you there's a tactic.

Ordinary puzzle sites announce that a tactic exists, which removes the hardest part of finding it. This tool takes
the mistakes from **your own games**, adds quiet positions where nothing is there, and makes you decide
**"Is there a tactic here?"** before you may move. It is built for players who solve puzzles well but still walk
past opportunities in real games.

> **Status: early release.** It works for its author, but parts have had limited testing. Please report
> problems as issues.

## What it does

- Analyses games from a **Lichess account** or any **PGN file** with Stockfish.
- Finds missed mates, missed wins, blunders, and mistakes, and turns them into puzzles.
- Adds quiet positions, so "no" is sometimes the right answer.
- Lets you **play out the engine's line**, step through it with the arrow keys, and explore freely afterwards.
- Shows **Stockfish arrows and evaluations** after you solve a puzzle (local server mode).
- Tags tactics and mate patterns (fork, pin, skewer, discovered attack, back-rank, smothered, Arabian, and more).
- Tracks your progress with spaced repetition, a log of every attempt, notes on why you missed things, and a stats page.
- Filters by type, pattern, colour, opponent, game, and date. Includes timed rounds.
- Runs entirely on your own computer. Your games and results are not uploaded anywhere.

## Quick start

New to the command line? Read **[GETTING_STARTED.md](GETTING_STARTED.md)**: it walks through installing
Python, the chess library, and Stockfish, step by step.

If you already know your way around:

```
pip install chess
# unzip Stockfish into a folder named "stockfish" next to pgn_puzzles.py
python pgn_puzzles.py --lichess YourLichessName --max 5 --no-open
python pgn_puzzles.py --serve
```

Then open http://localhost:8765/. Try it without an account using the sample games:

```
python pgn_puzzles.py examples/sample.pgn --player "SamplePlayer" --no-open
python pgn_puzzles.py --serve
```

Every command and option is explained in **[COMMANDS.md](COMMANDS.md)**.

## How it fits together

| File | Role |
|---|---|
| `pgn_puzzles.py` | Analysis, the puzzle library, Lichess import, pattern detection, local server |
| `trainer_template.html` | The whole trainer page (board, line play, filters, stats) |
| `assets.json` | Bundled chess rules and piece images, inserted into the page |
| `puzzles.json` | Your puzzle library (created on first run, not part of the project) |

More detail: **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** explains each part and the data formats,
and **[MAINTENANCE.md](MAINTENANCE.md)** covers updating, changing, testing, and releasing.

The analysis step runs once per game and is the slow part. The trainer page never re-runs it, so you can change
the page and rebuild in seconds.

## Known limits

- Engine lines are stored up to six half-moves, so mate patterns are only recognised for short mates.
- Tactic tags (fork, skewer, and so on) come from rules, not understanding, and are sometimes wrong.
- Chess.com import is not built yet. You can export a PGN from Chess.com and use the PGN route.
- Training progress is stored in your browser. Use **Export progress** to back it up.

## Credits and license

Licensed under the GNU General Public License v3.0 or later. See [THIRD_PARTY.md](THIRD_PARTY.md) for the
components this project builds on. Stockfish is not included; download it from its official site.
