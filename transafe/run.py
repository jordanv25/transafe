"""Start Transafe:  python run.py  [--port 8000] [--no-browser]"""
import argparse
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app.nlp.models import BUNDLE_PATH, train_all


def announce_when_ready(host, port, open_browser):
    """The server only starts answering after start-up (loading the simulated history takes a while), so wait for it
    instead of opening the browser too early."""
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{shown}:{port}"
    for _ in range(600):
        try:
            urllib.request.urlopen(url + "/api/meta", timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        return
    print(f"[run] ready: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--retrain", action="store_true", help="force re-training of all models")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.retrain or not BUNDLE_PATH.exists():
        print("[run] training models (about 15 seconds)...", flush=True)
        train_all()
    print("[run] starting: loading simulated history (about 20-60 seconds; TRANSAFE_BACKFILL_HOURS=3 is faster). "
          "The page opens when the server is ready.", flush=True)
    threading.Thread(target=announce_when_ready, args=(args.host, args.port, not args.no_browser), daemon=True).start()
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="warning")
