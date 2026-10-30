"""Start TransitPulse:  python run.py  [--port 8000] [--no-browser]"""
import argparse
import threading
import webbrowser

import uvicorn

from app.nlp.models import BUNDLE_PATH, train_all

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--retrain", action="store_true", help="force re-training of all models")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.retrain or not BUNDLE_PATH.exists():
        print("[run] training models (about 10 seconds)...")
        train_all()
    if not args.no_browser:
        threading.Timer(2.5, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="warning")
