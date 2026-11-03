# Getting started

This guide assumes you have never used a command line or installed Python. Take it one step at a time.
It takes about 20 minutes the first time.

## What this is

A training tool that turns the mistakes in your own chess games into puzzles. A computer engine (Stockfish)
finds the moves you missed, and a trainer page in your web browser lets you practise them. Everything runs on
your own computer. Nothing is uploaded anywhere; the only internet connection is the optional download of
your games from Lichess.

## What you need

- A Windows, Mac, or Linux computer
- Python (free), the Python chess library (free), and the Stockfish engine (free)
- Some games to analyse: a Lichess account, or a PGN file (a text file of games that most chess sites can export)

## A few words explained

- **Terminal / command line:** a window where you type instructions instead of clicking. On Windows it is called
  *PowerShell* (or *Command Prompt*); on Mac and Linux it is called *Terminal*. Everything you type there is a
  **command**, followed by pressing **Enter**.
- **Folder path:** the address of a folder, for example `C:\chess-trainer` on Windows or `/home/you/chess-trainer` on Linux.
- **Project folder:** the folder where you put this tool's files. The commands must be run from inside it.

## Step 1: Install Python

1. Go to **https://www.python.org/downloads/** and download the latest Python 3 for your system.
   (A recent version, 3.9 or newer, is a safe choice.)
2. **Windows:** run the installer. On the very first screen, tick **"Add python.exe to PATH"** before clicking
   Install. This is the step people most often miss.
   **Mac:** open the downloaded installer and follow it. **Linux:** Python is usually already installed.
3. Check it worked. Open a terminal (see Step 3 if you don't know how) and type:

   - Windows: `python --version`
   - Mac / Linux: `python3 --version`

   You should see something like `Python 3.12.1`. If Windows says "python is not recognized", run the installer
   again, choose *Modify*, and make sure the PATH option is ticked, or try `py --version` instead.

> On Mac and Linux, use `python3` wherever this guide says `python`.

## Step 2: Put the project files in a folder

1. Create a folder where you want the tool to live, for example `C:\chess-trainer`.
2. Put these files in it: `pgn_puzzles.py`, `trainer_template.html`, and `assets.json`.
   (If the project is on GitHub, use the green **Code** button and **Download ZIP**, then unzip it.)
3. Keep them together. The script looks for the other two files next to itself.

## Step 3: Open a terminal inside that folder

- **Windows:** open the folder in File Explorer, click on the address bar at the top, type `powershell`, and
  press Enter. A blue window opens, already inside your folder. (Windows 11 also offers *Open in Terminal* when
  you right-click empty space in the folder.)
- **Mac:** open *Terminal*, type `cd ` (with a space after it), drag the folder from Finder into the window,
  and press Enter.
- **Linux:** right-click inside the folder and choose *Open in Terminal*.

The last line of the window shows where you are. It should end with your project folder's name.

## Step 4: Install the chess library

Type this and press Enter:

```
python -m pip install chess
```

You should see `Successfully installed chess-...` (or a message that it is already installed). If you see a
warning about "scripts not on PATH", you can ignore it.

## Step 5: Download Stockfish (the engine)

1. Go to **https://stockfishchess.org/download/**
2. Choose your system and download it.
   - **Windows:** pick the build with **avx2** in its name. It works on most computers made since about 2013.
     If it won't start, try the plain *x86-64* build.
   - **Mac:** pick the Apple Silicon (M1/M2/M3) build if you have a recent Mac, otherwise the Intel (x86-64) build.
   - **Linux:** you can usually install it with your package manager, for example `sudo apt install stockfish`.
3. The download is a zip file. Create a folder called `stockfish` **inside your project folder**
   (for example `C:\chess-trainer\stockfish\`) and unzip it there. The tool finds the engine program
   (for example `stockfish-windows-x86-64-avx2.exe`) automatically; there is nothing to edit.
4. If you keep Stockfish somewhere else, tell the tool where it is. Either add `--engine "FULL\PATH\TO\ENGINE"`
   to your commands, or create a plain text file called `settings.json` in the project folder containing
   (use your own path, with doubled backslashes on Windows):

   ```json
   {"engine": "C:\\tools\\stockfish\\stockfish-windows-x86-64-avx2.exe"}
   ```

   Linux with `apt install stockfish` works without any of this.
5. **Windows security warnings:** Windows or your antivirus may warn about a downloaded `.exe`. If you downloaded it from
   the official site above, choose *More info*, then *Run anyway* (or allow it in your antivirus). On a Mac,
   if macOS blocks the engine, open *System Settings > Privacy & Security* and allow it, and you may need to run
   `chmod +x` on the file.

## Step 6: Analyse your first games

**If you have a Lichess account**, start small. Replace `YourLichessName` with your username:

```
python pgn_puzzles.py --lichess YourLichessName --max 5 --no-open
```

It downloads your five most recent rapid or classical games, analyses them, and prints one line per game. This
takes a minute or two. The end should look something like:

```
5 games read, 5 analysed. 15 new puzzles added; library now has 15:
```

If you play mostly blitz or bullet, add `--perf all`.

**If you have a PGN file instead**, put it in your project folder and run (replace the file name and your name
exactly as they appear in the PGN):

```
python pgn_puzzles.py my_games.pgn --player "YourName" --no-open
```

Larger imports take a long time (the engine checks every move). Start with a few games, check that it works,
then import more.

## Step 7: Start the trainer

```
python pgn_puzzles.py --serve
```

Your web browser opens at **http://localhost:8765/**. If it doesn't, type that address into the browser yourself.
Leave the terminal window open while you train; closing it stops the trainer. Press **Ctrl+C** in that window to
stop it when you're finished.

## Step 8: Using the trainer

- Each puzzle first asks **"Is there a tactic here?"** Decide before you move. Some positions have nothing in
  them; that is deliberate.
- If you say yes, click the piece, then its destination, or drag it. You get two tries. **Hint** shows the piece,
  then the square.
- After the first move you can keep playing the engine's line. Use the left and right arrow keys to step through
  the moves afterwards, and move the pieces freely to explore.
- **Try again** repeats a puzzle without scoring it. **Enter** goes to the next puzzle.
- Tag why you missed it, and check the **Stats** tab for your weak spots.
- With the engine running, **Engine arrows** shows the three best moves and their evaluations (plus is better
  for White, minus is better for Black).
- Click **Export progress** now and then. Your results are stored in your browser, and the export is your backup.

## Your routine from now on

1. After playing new games: `python pgn_puzzles.py --lichess YourLichessName --no-open`
2. Practise: `python pgn_puzzles.py --serve`

See `COMMANDS.md` for every command and option.

## If something goes wrong

| What you see | What to do |
|---|---|
| `'python' is not recognized` (Windows) | Python's PATH option wasn't ticked. Reinstall (see Step 1), or try `py` instead of `python`. |
| `command not found: python` (Mac/Linux) | Use `python3` instead of `python`. |
| `No module named chess` | Run Step 4 again. Make sure you use the same `python` for both. |
| `Stockfish not found` | Unzip Stockfish into a `stockfish` folder inside the project folder, or use `--engine` or `settings.json` (see Step 5). |
| `Can't find trainer_template.html` or `assets.json` | Those files must be in the same folder as `pgn_puzzles.py`. |
| `Can't find the PGN file` | Check the file name and that it's in the project folder. The message lists the PGN files it can see. |
| `Lichess has no user called ...` | Check the spelling of the username. |
| `Port 8765 is busy` | Another copy of the trainer is still running. Close it, or use `--port 8766` (you would need to export and import your progress once). |
| The page looks old or unchanged | Press **Ctrl+F5** in the browser to refresh fully. |
| Progress seems missing | Make sure you open the same address each time (`http://localhost:8765/`), and import your latest exported progress file. |
| The engine runs very slowly | Close other chess programs. Lower the work with `--depth 12`. |

## Privacy and backups

- Your puzzles, games, and settings stay on your computer. The tool only contacts Lichess when you ask it to import games.
- Back up two things now and then: your `puzzles.json` file, and the exported progress file from the trainer page.
- To update to a newer version of the tool later, replace the program files but keep your `puzzles.json`,
  `sync.json`, and `games` folder.
