"""Regenerate the README demo material in docs/: 5 screenshots and a 30-second GIF of an injected incident.

    pip install playwright pillow        # development tools only - NOT in requirements.txt
    python scripts/capture_demo.py       # needs Google Chrome or Microsoft Edge installed; takes about 3 minutes

What it does: starts the server on its own port in simulator mode (50 hours of history, so the time-of-day trend
baseline is active), speeds the clock up to 60x, waits a few calm seconds, injects a "Bus breakdown" and records the
dashboard for 30 seconds into docs/incident-demo.gif. Then it takes the screenshots (the Analyzer one with the Noise
slider at 50%). The data is simulated, as everywhere in the demo.

The calm seconds before the incident must show NO emerging alerts. Chance alerts do happen (see README, Limits), so the
script checks /api/state while it waits; if one shows up it throws that run away, restarts the server with the next
simulator seed (TRANSAFE_SEED = --seed, --seed + 1, ...) and tries again. Nothing in docs/ is touched by a failed run.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
VIEW = {"width": 1440, "height": 900}
SAMPLE = "Bus 335E broke down near Silk Board, stuck for 45 minutes, women and kids stranded. Please help!"
CALM_SECONDS = 3


class NotCalm(Exception):
    """An emerging-trend alert was showing before the incident was injected."""


def call(base, path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"null")


def alerts(base):
    """Labels currently shown in the Emerging-trends panel."""
    return [i["label"] for i in call(base, "/api/state")["snapshot"]["emerging"]["items"]]


def start_server(port, hours, python, seed):
    env = dict(os.environ, TRANSAFE_BACKFILL_HOURS=str(hours), TRANSAFE_SEED=str(seed),
               TRANSAFE_LIVE="0", TRANSAFE_SIM="1")
    proc = subprocess.Popen([python, "run.py", "--no-browser", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(180):                                   # the backfill takes up to a minute
        try:
            call(base, "/api/meta")
            return proc, base
        except Exception:
            if proc.poll() is not None:
                sys.exit("server exited early; run `python run.py` once to see the error")
            time.sleep(2)
    proc.terminate()
    sys.exit("server did not start within 6 minutes")


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()


def launch(pw):
    for kwargs in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return pw.chromium.launch(headless=True, **kwargs)
        except Exception:
            continue
    sys.exit("no browser found: install Google Chrome or Microsoft Edge (or run `playwright install chromium`)")


def make_gif(frames, path, width, colors):
    """frames: list of (png_bytes, seconds_shown). One shared palette keeps the colours steady and the file small."""
    from PIL import Image
    imgs = []
    for png, _ in frames:
        im = Image.open(io.BytesIO(png)).convert("RGB")
        imgs.append(im.resize((width, round(im.height * width / im.width)), Image.LANCZOS))
    ref = imgs[len(imgs) * 2 // 3].quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = [im.quantize(palette=ref, dither=Image.Dither.NONE) for im in imgs]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=[max(40, int(s * 1000)) for _, s in frames],
                loop=0, optimize=True, disposal=1)


def wait_calm(base, seconds):
    """Raise NotCalm if any alert shows up during `seconds`."""
    end = time.time() + seconds
    while time.time() < end:
        shown = alerts(base)
        if shown:
            raise NotCalm(", ".join(shown))
        time.sleep(0.25)


def record_incident(page, base, seconds, fps):
    frames, t0, injected, last = [], time.time(), False, None
    while time.time() - t0 < seconds:
        if not injected:
            if time.time() - t0 > CALM_SECONDS:            # a few calm seconds, then the incident
                page.select_option("#selIncident", "bus_breakdown")
                page.click("#btnIncident")
                injected = True
            elif alerts(base):
                raise NotCalm(", ".join(alerts(base)))
        png = page.screenshot(type="png")
        stamp = time.time()
        if last is not None:
            frames[-1] = (frames[-1][0], stamp - last)
        frames.append((png, 1.0 / fps))
        last = stamp
        time.sleep(max(0.0, 1.0 / fps - (time.time() - stamp)))
    return frames


def capture(args, seed):
    """One attempt with one simulator seed. Raises NotCalm (nothing written) if the start was not quiet."""
    from playwright.sync_api import sync_playwright
    print(f"seed {seed}: starting server with {args.hours:g} h of history ...")
    proc, base = start_server(args.port, args.hours, args.server_python, seed)
    try:
        call(base, "/api/simulator", {"auto_incidents": False, "speed": 60})
        with sync_playwright() as pw:
            browser = launch(pw)
            page = browser.new_page(viewport=VIEW)
            page.goto(base + "/", wait_until="networkidle")
            page.wait_for_selector("#livePill.on")
            wait_calm(base, 2)

            if not args.no_gif:
                print(f"  quiet start, recording {args.gif_seconds:.0f} s of the dashboard ...")
                frames = record_incident(page, base, args.gif_seconds, args.gif_fps)
                make_gif(frames, DOCS / "incident-demo.gif", args.gif_width, args.gif_colors)
                print(f"  {len(frames)} frames -> docs/incident-demo.gif ({(DOCS / 'incident-demo.gif').stat().st_size / 1e6:.1f} MB)")
            else:                                          # screenshots still want an active incident
                page.click("#btnIncident")
                time.sleep(25)

            page.screenshot(path=DOCS / "dashboard.png", full_page=True)

            page.click('#tabs button[data-page="issues"]')
            page.wait_for_selector("#issueTable tbody tr")
            time.sleep(1)
            page.screenshot(path=DOCS / "issues.png", full_page=True)
            page.click("#issueTable tbody tr")
            page.wait_for_selector("#drawer.open, #drawer[aria-hidden='false']")
            time.sleep(1.5)
            page.screenshot(path=DOCS / "issue-detail.png")
            page.click("#drawerClose")

            page.click('#tabs button[data-page="analyzer"]')
            page.fill("#azText", SAMPLE)
            page.click("#azRun")
            page.wait_for_selector("#azResult:not([hidden])")
            page.evaluate("() => { const s = document.querySelector('#azNoise'); s.value = 50; s.dispatchEvent(new Event('input')); }")
            page.wait_for_selector(".side-by-side")
            time.sleep(1.5)
            page.screenshot(path=DOCS / "analyzer.png", full_page=True)

            page.click('#tabs button[data-page="model"]')
            page.wait_for_selector("#modelRoot .kpi")
            time.sleep(1)
            page.screenshot(path=DOCS / "model.png", full_page=True)
            browser.close()
    finally:
        stop_server(proc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--hours", type=float, default=50, help="hours of simulated history before the capture (>= 48.5 activates the time-of-day baseline)")
    ap.add_argument("--seed", type=int, default=11, help="first simulator seed to try")
    ap.add_argument("--max-attempts", type=int, default=8, help="seeds to try (seed, seed+1, ...) before giving up")
    ap.add_argument("--server-python", default=sys.executable, help="Python that has requirements.txt installed (default: this one)")
    ap.add_argument("--no-gif", action="store_true")
    ap.add_argument("--gif-seconds", type=float, default=30)
    ap.add_argument("--gif-width", type=int, default=960)
    ap.add_argument("--gif-fps", type=float, default=3)
    ap.add_argument("--gif-colors", type=int, default=160)
    args = ap.parse_args()

    DOCS.mkdir(exist_ok=True)
    for k in range(args.max_attempts):
        try:
            capture(args, args.seed + k)
        except NotCalm as e:
            print(f"  alert before the incident ({e}); trying the next seed")
            continue
        print(f"done with seed {args.seed + k}: no alerts before the incident. Files are in docs/")
        return
    sys.exit(f"no quiet start in {args.max_attempts} attempts; docs/ was not changed")


if __name__ == "__main__":
    main()
