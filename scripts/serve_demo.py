"""FREE demo server — the real web app with simulated LLM stages. Costs $0.

Serves the actual mobile page + REST API with every paid stage faked (LLM,
OCR, ASR) and the real API keys swapped for dummies, so you can click through
the whole experience — text, image, and voice — without an API key or a paisa
spent. Every submission returns the canned 5G/COVID verdict regardless of
input — that's expected; it's a UI demo, not a checker.

Run from the project root, then open http://127.0.0.1:8000
    .venv\\Scripts\\python.exe scripts\\serve_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_PATH", "./data/demo.db")
os.environ.setdefault("SEMANTIC_CACHE_ENABLED", "false")  # demo stays model-free

import uvicorn  # noqa: E402

from scripts.fake_stages import apply_fake_stages  # noqa: E402

apply_fake_stages()

from app.main import app  # noqa: E402  (import after patching)

if __name__ == "__main__":
    print(">> FREE demo mode: all LLM stages are simulated — $0, no keys needed.")
    print(">> Open http://127.0.0.1:8000 in your browser. Ctrl+C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
