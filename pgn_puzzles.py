#!/usr/bin/env python3
"""
pgn_puzzles.py - turn the mistakes in your own games into a puzzle trainer.

Reads any PGN file (one game or many, from any source), analyses it with
Stockfish, finds your missed mates, missed wins, blunders and mistakes, and
adds them to a growing library:
  puzzles.json  - the library (new puzzles are merged into it on every run)
  puzzles.html  - the trainer; open it in any browser (works offline)

The trainer page itself lives in trainer_template.html (keep it next to this
script). Edit that file to change the front end; no re-analysis is needed.

Usage (run from any folder; files are kept next to this script):
  python pgn_puzzles.py new_games.pgn --player "YourName"
  python pgn_puzzles.py a.pgn b.pgn --player name1 --player name2 --depth 16

Pass only NEW games each time. Old puzzles stay in the library.
Use --fresh to start a new library instead of adding to the old one.
Use --lichess USERNAME to download and analyse a Lichess account's new games
(e.g.  python pgn_puzzles.py --lichess myname --max 50 ). Games already analysed are
remembered in sync.json and skipped next time.
Use --serve to run the trainer at http://localhost:8765 with live Stockfish arrows.
Use --retag to (re)detect tactic and mate patterns on the whole library.
Use --rebuild to regenerate puzzles.html from the library without analysing
anything (after editing trainer_template.html):
  python pgn_puzzles.py --rebuild
Without --player, both sides of every game are analysed.
"""
import argparse
import hashlib
import json
import logging
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import chess
import chess.engine
import chess.pgn

# ---------------------------------------------------------------- settings

logging.getLogger("chess.pgn").setLevel(logging.CRITICAL)  # variant games are skipped; keep the console quiet
SCRIPT_DIR = Path(__file__).resolve().parent
CLAMP = 1000  # centipawn cap so a mate and a +10 position count the same

try:  # avoid crashes on Windows consoles when player names contain odd characters
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ----------------------------------------------------------------- helpers
def cp(score, color):
    """Centipawns from `color`'s point of view, capped at +-CLAMP."""
    v = score.pov(color).score(mate_score=10000)
    return max(-CLAMP, min(CLAMP, v))


def mate_in(score, color):
    """Plies to mate from `color`'s view (positive = color mates), else None."""
    return score.pov(color).mate()


def fmt_eval(score, color):
    m = mate_in(score, color)
    if m is not None:
        n = (abs(m) + 1) // 2
        return ("#%d" % n) if m > 0 else ("-#%d" % n)
    return "%+.1f" % (cp(score, color) / 100)


def pv_to_san(board, pv, n=6):
    b = board.copy()
    out = []
    for mv in pv[:n]:
        out.append(b.san(mv))
        b.push(mv)
    return out


def _local_engines():
    """Stockfish programs placed in a 'stockfish' folder next to this script."""
    base = SCRIPT_DIR / "stockfish"
    found = []
    if base.exists():
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.name.lower().startswith("stockfish"):
                if p.suffix.lower() == ".exe" or (p.suffix == "" and os.access(p, os.X_OK)):
                    found.append(str(p))
    return found


def _settings_engine():
    """Optional settings.json next to the script: {"engine": "full path to Stockfish"}."""
    path = SCRIPT_DIR / "settings.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("engine")
        except Exception:
            print("Warning: could not read settings.json; ignoring it.")
    return None


def find_engine(path):
    candidates = [path, _settings_engine(), os.environ.get("STOCKFISH_PATH")]
    candidates += _local_engines()
    candidates += [shutil.which("stockfish"), "/usr/games/stockfish",
                   "/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish"]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    sys.exit(
        "Stockfish not found.\n"
        "Easiest fix: unzip Stockfish into a folder called 'stockfish' next to this script.\n"
        "Or pass --engine \"FULL PATH\", or put {\"engine\": \"FULL PATH\"} in settings.json."
    )


def resolve_pgn(name):
    """Find the PGN in the current folder, then in the script's folder."""
    for base in (Path.cwd(), SCRIPT_DIR):
        p = (base / name) if not Path(name).is_absolute() else Path(name)
        if p.exists():
            return p
    here = sorted(p.name for p in SCRIPT_DIR.glob("*.pgn"))
    msg = "Can't find the PGN file: %s" % name
    if here:
        msg += "\nPGN files in %s:\n  %s" % (SCRIPT_DIR, "\n  ".join(here))
    else:
        msg += "\nNo .pgn files found in %s either." % SCRIPT_DIR
    sys.exit(msg)


# ---------------------------------------------------------------- analysis
def process_game(game, engine, args, rng):
    h = game.headers
    white, black = h.get("White", "?"), h.get("Black", "?")
    if h.get("Variant", "Standard") not in ("Standard", "From Position"):
        return None  # Stockfish analysis here is for standard chess only

    if args.player:
        names = [p.lower() for p in args.player]
        exact = getattr(args, "player_exact", False)
        match = (lambda n, who: n == who.lower()) if exact else (lambda n, who: n in who.lower())
        sides = set()
        if any(match(n, white) for n in names):
            sides.add(chess.WHITE)
        if any(match(n, black) for n in names):
            sides.add(chess.BLACK)
        if not sides:
            return None  # none of the players is in this game
    else:
        sides = {chess.WHITE, chess.BLACK}

    moves = list(game.mainline_moves())
    boards = [game.board()]
    for mv in moves:
        b = boards[-1].copy()
        b.push(mv)
        boards.append(b)

    cache = {}

    def analyse(i):
        if i not in cache:
            b = boards[i]
            if b.is_game_over():
                cache[i] = None
            else:
                cache[i] = engine.analyse(
                    b, chess.engine.Limit(depth=args.depth), multipv=args.multipv
                )
        return cache[i]

    puzzles, decoys = [], []
    info_game = {
        "white": white,
        "black": black,
        "date": h.get("Date", "?"),
        "site": h.get("Site", ""),
    }

    for i, mv in enumerate(moves):
        board = boards[i]
        color = board.turn
        if color not in sides or i < args.skip_plies:
            continue
        infos = analyse(i)
        if not infos:
            continue
        best = infos[0]
        best_cp = cp(best["score"], color)
        best_mate = mate_in(best["score"], color)
        if best_cp <= -500:
            continue  # already lost: blunders here make poor puzzles

        # moves that count as correct for the puzzle
        accept = []
        for inf in infos:
            m0 = inf["pv"][0]
            if best_mate is not None and best_mate > 0:
                mm = mate_in(inf["score"], color)
                ok = mm is not None and 0 < mm <= best_mate  # no slower mates
            else:
                ok = cp(inf["score"], color) >= best_cp - args.tolerance
            if ok:
                accept.append(m0)

        base = {
            "fen": board.fen(),
            "turn": "white" if color == chess.WHITE else "black",
            "move_no": board.fullmove_number,
            "game": info_game,
            "best_eval": fmt_eval(best["score"], color),
        }

        if mv in accept:
            # fine move; maybe usable as a "nothing here" position
            if (
                best_mate is None
                and abs(best_cp) <= 150
                and not board.is_check()
                and len(infos) >= 2
                and best_cp - cp(infos[1]["score"], color) < 60
            ):
                decoys.append((board, mv, best, base))
            continue

        # evaluate what actually happened
        nxt = boards[i + 1]
        if nxt.is_checkmate():
            continue
        after_mate, after_cp = None, 0
        if not nxt.is_game_over():
            a1 = analyse(i + 1)
            after_cp = cp(a1[0]["score"], color)
            after_mate = mate_in(a1[0]["score"], color)
        loss = best_cp - after_cp

        category = None
        if best_mate is not None and best_mate > 0:
            if after_mate is not None and after_mate > 0:
                if (after_mate + 1) - best_mate >= 4:
                    category = "long_route"
            else:
                category = "missed_mate"
        elif loss >= args.blunder:
            category = "missed_win" if (best_cp >= 300 and after_cp > -150) else "blunder"
        elif loss >= args.mistake:
            category = "mistake"
        if not category:
            continue

        best_move = best["pv"][0]
        puzzles.append(
            dict(
                base,
                category=category,
                best=best_move.uci(),
                best_san=board.san(best_move),
                accept=[m.uci() for m in accept],
                played_san=board.san(mv),
                loss=loss,
                pv=pv_to_san(board, best["pv"]),
            )
        )

    # a few quiet positions: the "is there anything here?" check needs answers of "no"
    for board, mv, best, base in rng.sample(decoys, min(args.decoys, len(decoys))):
        puzzles.append(
            dict(
                base,
                category="none",
                best=mv.uci(),
                best_san=board.san(mv),
                accept=[mv.uci()],
                played_san=board.san(mv),
                loss=0,
                pv=pv_to_san(board, best["pv"], 3),
            )
        )

    for p in puzzles:
        p["id"] = hashlib.sha1((p["fen"] + p["best"]).encode()).hexdigest()[:10]
        p["themes"] = tag_puzzle(p)
    return puzzles


# ----------------------------------------------------------------- trainer page
TEMPLATE_PATH = SCRIPT_DIR / "trainer_template.html"


def read_template():
    if not TEMPLATE_PATH.exists():
        sys.exit(
            "Can't find trainer_template.html.\n"
            "It must sit in the same folder as this script: %s" % SCRIPT_DIR
        )
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "__DATA__" not in tpl:
        sys.exit("trainer_template.html is missing the __DATA__ placeholder.")
    return tpl


def build_page(library, out_dir, tpl):
    assets_path = SCRIPT_DIR / "assets.json"
    if not assets_path.exists():
        sys.exit("Can't find assets.json (chess rules and piece images). Keep it next to this script.")
    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    chessjs = (
        "(function(){var module={exports:{}};var exports=module.exports;\n"
        + assets["chessjs"].replace("</", "<\\/")
        + "\n;window.Chess=module.exports.Chess;})();"
    )
    data = json.dumps(library).replace("</", "<\\/")
    page = tpl.replace("__DATA__", data, 1)  # first, so nothing inserted later can be mistaken for it
    page = page.replace("__PIECES__", json.dumps(assets["pieces"]), 1)
    page = page.replace("__CHESSJS__", chessjs, 1)
    html_path = out_dir / "puzzles.html"
    html_path.write_text(page, encoding="utf-8")
    return html_path


def open_page(html_path):
    try:
        webbrowser.open(html_path.resolve().as_uri())
    except Exception:
        pass


# ------------------------------------------------------------- themes
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def _sgn(v):
    return (v > 0) - (v < 0)


def _neighbors(sq):
    return [s for s in chess.SQUARES if chess.square_distance(s, sq) == 1]


def mate_patterns(b):
    """b = board right after the mating move. Returns pattern names."""
    out = []
    mated = b.turn
    mator = not mated
    k = b.king(mated)
    checkers = list(b.checkers())
    nb = _neighbors(k)
    kf, kr = chess.square_file(k), chess.square_rank(k)
    ck = [b.piece_type_at(s) for s in checkers]

    def own(s):
        p = b.piece_at(s)
        return p is not None and p.color == mated

    back = 0 if mated == chess.WHITE else 7
    if kr == back and len(checkers) == 1 and ck[0] in (chess.ROOK, chess.QUEEN) and chess.square_rank(checkers[0]) == back:
        front = [s for s in nb if chess.square_rank(s) != back]
        if front and all(own(s) for s in front):
            out.append("back_rank")
    if len(checkers) == 1 and ck[0] == chess.KNIGHT and all(own(s) for s in nb):
        out.append("smothered")
    if kf in (0, 7) and kr in (0, 7):
        rook_adj = any(
            t == chess.ROOK and chess.square_distance(c, k) == 1
            and (chess.square_file(c) == kf or chess.square_rank(c) == kr)
            for c, t in zip(checkers, ck)
        )
        knight = any(
            abs(chess.square_file(n) - kf) == 2 and abs(chess.square_rank(n) - kr) == 2
            for n in b.pieces(chess.KNIGHT, mator)
        )
        if rook_adj and knight:
            out.append("arabian")
    if kf in (0, 7):
        d = 1 if kf == 0 else -1
        on_file = any(t in (chess.ROOK, chess.QUEEN) and chess.square_file(c) == kf for c, t in zip(checkers, ck))
        adj = chess.square(kf + d, kr)
        kn = chess.square(kf + 3 * d, kr)
        pk = b.piece_at(kn)
        if on_file and own(adj) and pk and pk.piece_type == chess.KNIGHT and pk.color == mator:
            out.append("anastasia")
    bishops = list(b.pieces(chess.BISHOP, mator))
    if len(bishops) >= 2 and chess.BISHOP in ck:
        chk = [c for c, t in zip(checkers, ck) if t == chess.BISHOP]
        others = [x for x in bishops if x not in chk]
        if others and any(n in b.attacks(x) for x in others for n in nb):
            out.append("double_bishop")
    return out


def _discovered(before, after, mv, color):
    opp = not color
    for st in SLIDERS:
        for s in before.pieces(st, color):
            if s == mv.from_square:
                continue
            for t in after.attacks(s):
                pc = after.piece_at(t)
                if (pc and pc.color == opp and VAL[pc.piece_type] >= 3
                        and t not in before.attacks(s)
                        and mv.from_square in chess.SquareSet(chess.between(s, t))):
                    return True
    return False


def first_move_themes(before, mv, after, color):
    out = []
    opp = not color
    to = mv.to_square
    pt = after.piece_type_at(to)
    cap = before.piece_at(to)
    if cap and cap.color == opp and VAL[cap.piece_type] >= 3 and not before.attackers(opp, to):
        out.append("hanging_piece")
    if pt != chess.KING:
        good = []
        for t in after.attacks(to):
            pc = after.piece_at(t)
            if pc and pc.color == opp and VAL[pc.piece_type] >= 3 and (
                VAL[pc.piece_type] > VAL[pt] or not after.attackers(opp, t)
            ):
                good.append(t)
        if len(good) >= 2:
            out.append("fork")
    if pt in SLIDERS:
        for s in chess.SQUARES:
            pc = after.piece_at(s)
            if pc and pc.color == opp and pc.piece_type != chess.KING and after.is_pinned(opp, s) and to in after.pin(opp, s):
                out.append("pin")
                break
        done = False
        for x in after.attacks(to):
            px = after.piece_at(x)
            if done or not px or px.color != opp:
                continue
            df = _sgn(chess.square_file(x) - chess.square_file(to))
            dr = _sgn(chess.square_rank(x) - chess.square_rank(to))
            f, r = chess.square_file(x) + df, chess.square_rank(x) + dr
            while 0 <= f < 8 and 0 <= r < 8:
                py = after.piece_at(chess.square(f, r))
                if py:
                    if py.color == opp and VAL[px.piece_type] > VAL[py.piece_type] and VAL[py.piece_type] >= 3:
                        out.append("skewer")
                        done = True
                    break
                f += df
                r += dr
    if _discovered(before, after, mv, color):
        out.append("discovered_attack")
    return out


def tag_puzzle(p):
    """Theme tags for one puzzle, from its start position and engine line."""
    if p.get("category") == "none":
        return []
    themes = []
    try:
        b = chess.Board(p["fen"])
        color = b.turn
        for i, san in enumerate(p["pv"]):
            mv = b.parse_san(san)
            before = b.copy()
            b.push(mv)
            if i == 0:
                themes += first_move_themes(before, mv, b, color)
            if b.is_checkmate():
                if b.turn != color:
                    themes += mate_patterns(b)
                break
    except Exception:
        pass
    if str(p.get("best_eval", "")).startswith("#"):
        themes.insert(0, "mate")
    return list(dict.fromkeys(themes))


def retag_all(library):
    for p in library:
        p["themes"] = tag_puzzle(p)
    return sum(1 for p in library if p["themes"])


# ----------------------------------------------------------------- library
def load_library(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("not a list")
        return data
    except Exception as e:
        sys.exit(
            "Could not read your existing library (%s): %s\n"
            "Nothing was changed. Fix or move that file, or use --fresh." % (path, e)
        )


def save_library(path, puzzles):
    if path.exists():  # keep one backup of the previous library
        shutil.copyfile(path, path.with_name("puzzles.backup.json"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(puzzles, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# ------------------------------------------------------- sync + Lichess import
USER_AGENT = "missed-tactics-trainer/0.1 (personal chess training tool)"
RATE_WAIT = int(os.environ.get("MT_RATE_WAIT", "60"))  # seconds to wait after HTTP 429


def new_sync():
    return {"version": 1, "analysed": [], "lichess": {}}


def load_sync(out_dir):
    path = out_dir / "sync.json"
    if not path.exists():
        return new_sync()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("analysed", [])
        data.setdefault("lichess", {})
        return data
    except Exception as e:
        print("Warning: could not read %s (%s); starting with an empty sync record." % (path, e))
        return new_sync()


def save_sync(out_dir, sync):
    path = out_dir / "sync.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(sync, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def game_key(game):
    """Stable identity for a game: its Site URL if it has one, else a hash of its headers."""
    h = game.headers
    site = h.get("Site", "")
    if site.startswith("http"):
        return site
    plies = sum(1 for _ in game.mainline_moves())
    raw = "|".join([h.get("White", ""), h.get("Black", ""), h.get("Date", ""),
                    h.get("UTCTime", h.get("StartTime", "")), h.get("Result", ""), str(plies)])
    return "h:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def game_ts_ms(h):
    d = h.get("UTCDate") or h.get("Date", "")
    t = h.get("UTCTime", "00:00:00")
    try:
        dt = datetime.strptime(d + " " + t, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def parse_since(text):
    try:
        dt = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        sys.exit("--since must look like 2026-09-01")
    return int(dt.timestamp() * 1000)


def download_lichess(user, since_ms, max_games, perfs, token, host, dest):
    """Stream a user's games from the Lichess API into dest (PGN)."""
    params = {"max": max_games, "clocks": "false", "evals": "false", "opening": "false"}
    if perfs:
        params["perfType"] = perfs
    if since_ms:
        params["since"] = since_ms
        params["sort"] = "dateAsc"  # oldest new games first, so later runs continue where this one stopped
    url = "%s/api/games/user/%s?%s" % (host.rstrip("/"), urllib.parse.quote(user), urllib.parse.urlencode(params))
    headers = {"Accept": "application/x-chess-pgn", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = "Bearer " + token
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            return dest
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                print("Lichess asked us to slow down (HTTP 429). Waiting %d seconds..." % RATE_WAIT)
                time.sleep(RATE_WAIT)
                continue
            if e.code == 404:
                sys.exit("Lichess has no user called %r." % user)
            if e.code == 401:
                sys.exit("Lichess rejected the token. Check --token or the LICHESS_TOKEN variable.")
            sys.exit("Lichess returned HTTP %d." % e.code)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            sys.exit("Could not reach Lichess: %s" % e)
    sys.exit("Lichess kept refusing the request. Try again in a few minutes.")


# ------------------------------------------------------------------ server
def serve(args, out, lib_path, tpl):
    """Serve the trainer on localhost and keep Stockfish running for live analysis."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    library = load_library(lib_path)
    if not library:
        sys.exit("No library found at %s. Analyse some games first." % lib_path)
    html_path = build_page(library, out, tpl)
    engine = chess.engine.SimpleEngine.popen_uci(find_engine(args.engine))
    try:
        engine.configure({"Threads": args.threads, "Hash": 128})
    except Exception:
        pass
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            b = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/puzzles.html"):
                self._send(200, html_path.read_bytes(), "text/html; charset=utf-8")
            elif u.path == "/ping":
                self._send(200, "ok", "text/plain")
            elif u.path == "/analyse":
                try:
                    board = chess.Board(parse_qs(u.query)["fen"][0])
                    lines = []
                    if not board.is_game_over():
                        with lock:
                            infos = engine.analyse(board, chess.engine.Limit(time=args.think), multipv=3)
                        for inf in infos:
                            if inf.get("pv"):
                                m = inf["pv"][0]
                                lines.append({
                                    "from": chess.square_name(m.from_square),
                                    "to": chess.square_name(m.to_square),
                                    "san": board.san(m),
                                    "eval": fmt_eval(inf["score"], chess.WHITE),
                                })
                    self._send(200, json.dumps({"lines": lines}), "application/json")
                except Exception as e:
                    self._send(400, json.dumps({"error": str(e)}), "application/json")
            else:
                self._send(404, "not found", "text/plain")

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        engine.quit()
        sys.exit("Port %d is busy. Try --port 8766." % args.port)
    url = "http://localhost:%d/" % args.port
    print("Trainer running at %s (Stockfish is live). Press Ctrl+C to stop." % url)
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        engine.quit()


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Turn your game mistakes into puzzles.")
    ap.add_argument("pgn", nargs="*", help="PGN file(s), one or many games each")
    ap.add_argument("--player", action="append", help="your name as in the PGN (repeatable, partial match ok)")
    ap.add_argument("--engine", help="path to Stockfish (default: found automatically)")
    ap.add_argument("--depth", type=int, default=14, help="engine depth (default 14; 12 is faster, 16-18 is stronger)")
    ap.add_argument("--multipv", type=int, default=3, help="lines per position, used to accept alternative solutions")
    ap.add_argument("--blunder", type=int, default=250, help="centipawn loss counted as a blunder / missed win")
    ap.add_argument("--mistake", type=int, default=120, help="centipawn loss counted as a mistake")
    ap.add_argument("--tolerance", type=int, default=30, help="alternatives within this many cp of best also count as correct")
    ap.add_argument("--skip-plies", type=int, default=8, help="ignore the first N half-moves (opening book)")
    ap.add_argument("--decoys", type=int, default=1, help="quiet 'nothing here' positions per game (0 = none)")
    ap.add_argument("--threads", type=int, default=2, help="engine threads (use up to your CPU core count)")
    ap.add_argument("--out-dir", default=str(SCRIPT_DIR), help="where the library lives (default: next to this script)")
    ap.add_argument("--fresh", action="store_true", help="ignore the existing library and start a new one")
    ap.add_argument("--rebuild", action="store_true", help="regenerate puzzles.html from the library; no PGN or analysis needed")
    ap.add_argument("--retag", action="store_true", help="re-detect tactic and mate patterns for every puzzle in the library, then rebuild the page")
    ap.add_argument("--serve", action="store_true", help="run the trainer on localhost with live Stockfish arrows and evals")
    ap.add_argument("--port", type=int, default=8765, help="port for --serve (keep it the same so your progress stays put)")
    ap.add_argument("--think", type=float, default=0.8, help="seconds of engine thinking per position in --serve mode")
    ap.add_argument("--lichess", metavar="USERNAME", help="download this Lichess user's games and analyse the new ones")
    ap.add_argument("--since", help="with --lichess: only games from this date on (YYYY-MM-DD)")
    ap.add_argument("--max", type=int, default=100, dest="max_games", help="with --lichess: most games to download per run (default 100)")
    ap.add_argument("--perf", default="rapid,classical", help="with --lichess: game types, comma separated (default rapid,classical; use 'all' for everything)")
    ap.add_argument("--token", default=os.environ.get("LICHESS_TOKEN"), help="optional Lichess API token (or set LICHESS_TOKEN)")
    ap.add_argument("--reanalyse", action="store_true", help="analyse games even if they were analysed before")
    ap.add_argument("--lichess-host", default="https://lichess.org", help=argparse.SUPPRESS)
    ap.add_argument("--no-open", action="store_true", help="don't open the trainer in the browser when done")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lib_path = out / "puzzles.json"
    tpl = read_template()

    if args.serve:
        serve(args, out, lib_path, tpl)
        return

    if args.rebuild or args.retag:
        library = load_library(lib_path)
        if not library:
            sys.exit("No library found at %s. Analyse some games first." % lib_path)
        if args.retag:
            n = retag_all(library)
            save_library(lib_path, library)
            print("Pattern tags found on %d of %d puzzles." % (n, len(library)))
        html_path = build_page(library, out, tpl)
        print("Rebuilt the trainer from %d puzzles: %s" % (len(library), html_path))
        if not args.no_open:
            open_page(html_path)
        return

    if not args.pgn and not args.lichess:
        ap.error("give at least one PGN file, use --lichess USERNAME, or use --rebuild")
    pgn_paths = [resolve_pgn(p) for p in args.pgn]
    existing = [] if args.fresh else load_library(lib_path)
    sync = new_sync() if args.fresh else load_sync(out)
    analysed = set(sync["analysed"])
    for p in existing:  # puzzles remember their game's Site URL, so older runs count as analysed too
        site = (p.get("game") or {}).get("site", "")
        if site.startswith("http"):
            analysed.add(site)

    lichess_file, user = None, None
    if args.lichess:
        user = args.lichess.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,30}", user):
            sys.exit("%r doesn't look like a Lichess username." % user)
        since = None
        if args.since:
            since = parse_since(args.since)
        else:
            last = sync["lichess"].get(user.lower(), {}).get("last")
            if last:
                since = last + 1
        perfs = None if args.perf.lower() == "all" else args.perf.replace(" ", "")
        if args.max_games > 300:
            print("Note: %d games will take a long time to analyse. Consider a smaller --max." % args.max_games)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = out / "games" / ("lichess_%s_%s.pgn" % (user.lower(), stamp))
        print("Downloading %s's games from Lichess%s..." % (user, " since " + datetime.fromtimestamp(since / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC" if since else ""))
        lichess_file = download_lichess(user, since, args.max_games, perfs, args.token, args.lichess_host, dest)
        if lichess_file.stat().st_size == 0:
            lichess_file.unlink()
            print("No new games on Lichess for these settings. Nothing to do.")
            return
        pgn_paths.append(lichess_file)
        if not args.player:
            args.player = [user]
            args.player_exact = True

    rng = random.Random(args.seed)
    engine = chess.engine.SimpleEngine.popen_uci(find_engine(args.engine))
    try:
        engine.configure({"Threads": args.threads, "Hash": 128})
    except Exception:
        pass

    new_puzzles, n_games, n_used, n_old = [], 0, 0, 0
    interrupted, max_ts = False, None
    try:
        try:
            for path in pgn_paths:
                with open(path, encoding="utf-8-sig", errors="replace") as fh:
                    while True:
                        game = chess.pgn.read_game(fh)
                        if game is None:
                            break
                        n_games += 1
                        label = "%s - %s" % (game.headers.get("White", "?"), game.headers.get("Black", "?"))
                        if path == lichess_file:
                            ts = game_ts_ms(game.headers)
                            if ts and (max_ts is None or ts > max_ts):
                                max_ts = ts
                        key = game_key(game)
                        if key in analysed and not args.reanalyse:
                            n_old += 1
                            continue
                        res = process_game(game, engine, args, rng)
                        if res is None:
                            print("[%d] skipped (not your game, or not standard chess): %s" % (n_games, label))
                            continue
                        analysed.add(key)
                        n_used += 1
                        new_puzzles.extend(res)
                        print("[%d] %s -> %d puzzles" % (n_games, label, len(res)))
                        if game.errors:
                            print("    note: this PGN has a problem (such as an illegal move); it was analysed only up to that point")
        except KeyboardInterrupt:
            interrupted = True
            print("\nStopped early. Saving what has been analysed so far...")
    finally:
        engine.quit()

    sync["analysed"] = sorted(analysed)
    if user and max_ts and not interrupted:
        sync["lichess"][user.lower()] = {"last": max_ts}
    save_sync(out, sync)

    # merge: the existing library comes first, so old puzzles are always kept
    seen = {p.get("id") for p in existing}
    library, added = list(existing), 0
    for p in new_puzzles:
        if p["id"] not in seen:
            seen.add(p["id"])
            library.append(p)
            added += 1

    save_library(lib_path, library)
    html_path = build_page(library, out, tpl)

    counts = {}
    for p in library:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    print("\n%d games read, %d analysed%s. %d new puzzles added; library now has %d:" % (n_games, n_used, (", %d already analysed (skipped)" % n_old) if n_old else "", added, len(library)))
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  %-12s %d" % (k, v))
    print("\nTrainer: %s" % html_path)
    if not args.no_open:
        open_page(html_path)


if __name__ == "__main__":
    main()
