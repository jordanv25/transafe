"""Central configuration and shared constants for Transafe."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
DB_PATH = ROOT / "data_store.sqlite3"
STATIC_DIR = ROOT / "static"

MODEL_DIR.mkdir(exist_ok=True)

# Complaint categories (the 8 actionable ones + "other" for praise / queries / noise)
CATEGORIES = [
    "overcrowding",
    "delay",
    "safety",
    "driver_behavior",
    "vehicle_condition",
    "fare_ticketing",
    "breakdown",
    "accessibility",
    "other",
]
ACTIONABLE = [c for c in CATEGORIES if c != "other"]

CATEGORY_LABELS = {
    "overcrowding": "Overcrowding",
    "delay": "Delays",
    "safety": "Safety & Harassment",
    "driver_behavior": "Driver / Staff Behaviour",
    "vehicle_condition": "Vehicle Condition",
    "fare_ticketing": "Fare & Ticketing",
    "breakdown": "Breakdown / Cancellation",
    "accessibility": "Accessibility & Stops",
    "other": "Praise / Query / Other",
}

# Categorical colours (validated dark-mode palette, fixed order, one per category)
CATEGORY_COLORS = {
    "overcrowding": "#3987e5",
    "delay": "#d95926",
    "safety": "#e66767",
    "driver_behavior": "#9085e9",
    "vehicle_condition": "#c98500",
    "fare_ticketing": "#d55181",
    "breakdown": "#199e70",
    "accessibility": "#008300",
    "other": "#8a8a85",
}

SEVERITY_LEVELS = [(78, "critical"), (55, "high"), (30, "medium"), (0, "low")]

SOURCES = ["X / Twitter", "Complaint Portal", "WhatsApp Helpline", "Mobile App", "Call Centre"]
SOURCE_WEIGHTS = [0.34, 0.24, 0.16, 0.18, 0.08]

TIMEZONE = "Asia/Kolkata"
