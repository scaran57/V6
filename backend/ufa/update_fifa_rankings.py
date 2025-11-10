#!/usr/bin/env python3
# /app/backend/ufa/update_fifa_rankings.py
import os
import json
import time
import logging
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = "/app/logs/fifa_update.log"
Path("/app/logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [FIFA_UPDATE] %(message)s")

API_KEY = os.getenv("FIFA_API_KEY")
API_URL = os.getenv("FIFA_API_URL", "https://api.football-data.org/v4/competitions/FIFA/rankings")
OUT_FILE = Path(os.getenv("WORLD_COEFF_FILE", "/app/data/world_coeffs.json"))
TMP_FILE = OUT_FILE.with_suffix(".tmp.json")

MIN_COEFF = float(os.getenv("MIN_WORLD_COEFF", 0.85))
MAX_COEFF = float(os.getenv("MAX_WORLD_COEFF", 1.30))

def fetch_rankings():
    headers = {}
    if API_KEY:
        headers["X-Auth-Token"] = API_KEY
    try:
        logging.info("Fetching world rankings from API: %s", API_URL)
        resp = requests.get(API_URL, headers=headers, timeout=20)
        if resp.status_code != 200:
            logging.error("API returned %s: %s", resp.status_code, resp.text)
            return None
        return resp.json()
    except Exception as e:
        logging.exception("Error contacting FIFA API")
        return None

def parse_rankings(payload):
    rank_map = {}
    try:
        # Heuristics for multiple possible payload shapes.
        if not payload:
            return rank_map
        # Try "rankings" shape: list of {"team": {"name":...}, "rank": ...}
        if isinstance(payload, dict) and "rankings" in payload and isinstance(payload["rankings"], list):
            for item in payload["rankings"]:
                name = None
                rank = None
                if isinstance(item.get("team"), dict):
                    name = item["team"].get("name")
                name = name or item.get("country") or item.get("teamName") or item.get("name")
                rank = item.get("rank") or item.get("position")
                if name and rank:
                    rank_map[name] = int(rank)
            if rank_map:
                return rank_map

        # Try football-data.org structure: maybe payload contains lists or nested
        # e.g. payload may contain 'standings' with 'table' -> 'team' etc.
        if isinstance(payload, dict):
            # scan recursively for team lists with positions
            def scan_obj(obj):
                if isinstance(obj, dict):
                    if "table" in obj and isinstance(obj["table"], list):
                        for t in obj["table"]:
                            team = t.get("team") or {}
                            name = team.get("name") or t.get("teamName")
                            pos = t.get("position") or t.get("rank")
                            if name and pos:
                                rank_map[name] = int(pos)
                    else:
                        for v in obj.values():
                            scan_obj(v)
                elif isinstance(obj, list):
                    for it in obj:
                        scan_obj(it)
            scan_obj(payload)
            if rank_map:
                return rank_map

        # Fallback: if payload has 'teams' list
        if isinstance(payload, dict) and "teams" in payload and isinstance(payload["teams"], list):
            for idx, t in enumerate(payload["teams"], start=1):
                name = t.get("name") or t.get("teamName")
                if name:
                    rank_map[name] = idx
            return rank_map

    except Exception:
        logging.exception("Error parsing rankings payload")
    return rank_map

def compute_coeffs_from_ranks(rank_map):
    if not rank_map:
        return {}
    sorted_items = sorted(rank_map.items(), key=lambda x: x[1])  # ascending rank (1 top)
    N = len(sorted_items)
    coeff_map = {}
    for name, rank in sorted_items:
        if N > 1:
            coef = MIN_COEFF + ((N - rank) / (N - 1)) * (MAX_COEFF - MIN_COEFF)
        else:
            coef = (MIN_COEFF + MAX_COEFF) / 2
        coef = max(MIN_COEFF, min(MAX_COEFF, round(coef, 3)))
        coeff_map[name] = {"rank": int(rank), "coeff": coef}
    return coeff_map

def save_coeffs(coeff_map, source="api"):
    payload = {
        "updated": int(time.time()),
        "source": source,
        "teams": coeff_map
    }
    try:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TMP_FILE.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        TMP_FILE.replace(OUT_FILE)
        logging.info("Saved world coeffs to %s (%d teams).", OUT_FILE, len(coeff_map))
    except Exception:
        logging.exception("Error saving world coeffs")

def load_fallback():
    if OUT_FILE.exists():
        try:
            with OUT_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logging.exception("Failed loading fallback world coeffs")
    return {}

def update_world_coeffs():
    payload = fetch_rankings()
    if not payload:
        logging.warning("No payload from API, using fallback.")
        return load_fallback()
    rank_map = parse_rankings(payload)
    if not rank_map:
        logging.warning("Parsed rank_map empty, using fallback.")
        return load_fallback()
    coeffs = compute_coeffs_from_ranks(rank_map)
    save_coeffs(coeffs, source="api")
    return {"teams": coeffs, "source": "api"}

if __name__ == "__main__":
    res = update_world_coeffs()
    if res and "teams" in res:
        print("Update complete. Teams:", len(res["teams"]))
    else:
        print("Update failed or fallback used.")
