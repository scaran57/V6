#!/usr/bin/env python3
# /app/backend/ufa/ufa_auto_validate.py
"""
UFA Auto-Validate & Auto-Train
--------------------------------
Vérifie automatiquement les nouveaux scores réels depuis l'API Football-Data.org,
compare avec les matchs OCR avant-match, valide les correspondances,
et déclenche l'apprentissage UFA.

Intègre la clé API et un délai automatique entre chaque requête pour rester
dans les limites du forfait gratuit.

Usage:
    python /app/backend/ufa/ufa_auto_validate.py
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz, process
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# =========================================
# ⚙️ CONFIGURATION GÉNÉRALE
# =========================================

API_KEY = "ad9959577fd349ba99b299612668a5cb"
API_URL = "https://api.football-data.org/v4/matches"
DATA_FILE = "/app/data/real_scores.jsonl"
TEAM_MAP_FILE = "/app/data/team_map.json"
LOG_FILE = "/app/logs/ufa_auto_train.log"

# Délai entre requêtes (6 sec minimum pour plan gratuit)
REQUEST_DELAY = 6

# Thresholds
FUZZY_THRESHOLD = 80
DUPLICATE_WINDOW_DAYS = 7

# ---------- Helper utils ----------
def _log(msg: str):
    ts = datetime.datetime.utcnow().isoformat()
    line = f"[UFA-AUTO] {ts} - {msg}\n"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())

def load_team_map() -> Dict[str, str]:
    if TEAM_MAP_FILE.exists():
        try:
            raw = json.loads(TEAM_MAP_FILE.read_text(encoding="utf-8"))
            return {k.lower(): v for k, v in raw.items()}
        except Exception as e:
            _log(f"Erreur chargement team_map: {e}")
    return {}

def _normalize_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return str(s).strip()

def fuzzy_normalize(team: Optional[str], team_map: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (canonical_team_name, league) using map or fuzzy match.
    """
    if not team:
        return None, None
    low = team.lower()
    # exact map match
    if low in team_map:
        return low, team_map[low]
    # fuzzy match among keys
    keys = list(team_map.keys())
    if keys:
        cand = process.extractOne(low, keys)
        if cand and cand[1] >= FUZZY_THRESHOLD:
            matched = cand[0]
            return matched, team_map.get(matched)
    # fallback: return raw
    return low, None

def read_real_scores() -> List[Dict]:
    if not REAL_SCORES_FILE.exists():
        return []
    out = []
    with REAL_SCORES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # skip malformed lines but log
                _log(f"Malformed line skipped in {REAL_SCORES_FILE}: {line[:200]}")
    return out

def write_real_scores(entries: List[Dict]):
    temp = REAL_SCORES_FILE.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    temp.replace(REAL_SCORES_FILE)

def is_duplicate(new: Dict, existing: Dict) -> bool:
    """
    Duplicate heuristics:
      - same home+away (case-insensitive) and same league, and timestamps within DUPLICATE_WINDOW_DAYS
      - or exact same score and same teams same day
    """
    try:
        nh = (new.get("home_team") or "").lower()
        na = (new.get("away_team") or "").lower()
        eh = (existing.get("home_team") or "").lower()
        ea = (existing.get("away_team") or "").lower()
        if not nh or not na or not eh or not ea:
            return False
        if nh == eh and na == ea and (new.get("league") or "") == (existing.get("league") or ""):
            # compare dates if present
            tnew = _parse_iso(new.get("timestamp"))
            tex = _parse_iso(existing.get("timestamp"))
            if tnew and tex:
                diff = abs((tnew - tex).days)
                if diff <= DUPLICATE_WINDOW_DAYS:
                    return True
            else:
                # no timestamps => consider duplicate if scores match
                if new.get("home_goals") is not None and new.get("away_goals") is not None:
                    if new.get("home_goals") == existing.get("home_goals") and new.get("away_goals") == existing.get("away_goals"):
                        return True
    except Exception:
        return False
    return False

def _parse_iso(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
        except Exception:
            return None

def validate_score_format(h: Optional[int], a: Optional[int]) -> bool:
    if h is None or a is None:
        return False
    if not (MIN_GOAL <= h <= MAX_GOAL and MIN_GOAL <= a <= MAX_GOAL):
        return False
    return True

# ---------- Training trigger ----------
def trigger_training_via_api(match_payload: Dict) -> bool:
    try:
        # Note: /api/learn expects Form data, not JSON
        # We'll use the UFA trainer directly instead
        # For now, just skip API training and use script fallback
        _log(f"Skipping API training (endpoint expects Form data, not JSON)")
        return False
    except Exception as e:
        _log(f"Training API error: {e}")
        return False

def trigger_training_via_script(match_payload: Dict) -> bool:
    try:
        if not Path(TRAIN_SCRIPT).exists():
            _log(f"TRAIN_SCRIPT not found: {TRAIN_SCRIPT}")
            return False
        # call training script - you may adapt args to your script if needed
        cmd = ["python3", TRAIN_SCRIPT]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            _log(f"Training script executed successfully.")
            return True
        else:
            _log(f"Training script failed: rc={result.returncode} err={result.stderr[:400]}")
            return False
    except Exception as e:
        _log(f"Training script error: {e}")
        return False

# ---------- Core processing ----------
def process_pending_entries():
    team_map = load_team_map()
    entries = read_real_scores()
    if not entries:
        _log("No entries in real_scores.jsonl")
        return

    changed = False
    total_validated = 0
    total_triggered = 0

    # For duplicate detection, keep a copy of already-validated/trained entries
    existing_validated = [e for e in entries if e.get("validated") or e.get("trained")]
    pending = [e for e in entries if not (e.get("validated") or e.get("trained"))]

    _log(f"Found {len(pending)} pending entries, {len(existing_validated)} already validated/trained.")

    for idx, e in enumerate(pending):
        try:
            # sanitize values
            home = _normalize_name(e.get("home_team"))
            away = _normalize_name(e.get("away_team"))
            league = e.get("league") or None
            hgoals = e.get("home_goals")
            agoals = e.get("away_goals")

            # 1) validate score presence and format
            if not validate_score_format(hgoals, agoals):
                _log(f"Skipping entry #{idx} - invalid score: {home} vs {away} -> {hgoals}-{agoals}")
                e["validated"] = False
                e["validation_error"] = "invalid_score"
                changed = True
                continue

            # 2) normalize team names via map + fuzzy
            nh, nleague_h = fuzzy_normalize(home, team_map) if home else (None, None)
            na, nleague_a = fuzzy_normalize(away, team_map) if away else (None, None)

            # decide canonical name: prefer canonical from team_map if available, else original lower-case
            canonical_home = nh if nh else (home.lower() if home else None)
            canonical_away = na if na else (away.lower() if away else None)

            # update fields
            e["home_team_normalized"] = canonical_home
            e["away_team_normalized"] = canonical_away

            # 3) detect league if missing, prefer manual league if present
            if not league or league == "Unknown":
                # prefer league from team_map normalization
                if nleague_h and nleague_h == nleague_a:
                    detected_league = nleague_h
                else:
                    detected_league = nleague_h or nleague_a
                if not detected_league:
                    detected_league = "Unknown"
                league = detected_league
                e["league"] = league

            # 4) duplicate check against existing_validated + earlier pending processed
            duplicate_found = False
            for ex in existing_validated + pending:
                # skip self
                if ex is e:
                    continue
                if is_duplicate(e, ex):
                    duplicate_found = True
                    break
            if duplicate_found:
                e["validated"] = False
                e["validation_error"] = "duplicate"
                _log(f"Entry #{idx} marked duplicate: {canonical_home} vs {canonical_away} ({league})")
                changed = True
                continue

            # 5) mark validated and timestamp if OK
            e["validated"] = True
            e["validated_at"] = datetime.datetime.utcnow().isoformat()
            total_validated += 1
            changed = True
            _log(f"Validated: {canonical_home} vs {canonical_away} ({hgoals}-{agoals}) - {league}")

            # 6) prepare payload for training (minimal fields)
            payload = {
                "league": e.get("league"),
                "home_team": canonical_home,
                "away_team": canonical_away,
                "home_goals": hgoals,
                "away_goals": agoals,
                "source": e.get("source", "ocr_auto"),
                "timestamp": e.get("timestamp", datetime.datetime.utcnow().isoformat())
            }

            # 7) trigger training (prefer API)
            trained = False
            if TRAIN_API_URL:
                trained = trigger_training_via_api(payload)
            if not trained and TRAIN_SCRIPT:
                trained = trigger_training_via_script(payload)

            if trained:
                e["trained"] = True
                e["trained_at"] = datetime.datetime.utcnow().isoformat()
                total_triggered += 1
                _log(f"Training triggered for match: {canonical_home} vs {canonical_away}")
            else:
                _log(f"Training NOT triggered for match: {canonical_home} vs {canonical_away} (will retry next run)")

        except Exception as ex:
            _log(f"Error processing pending entry #{idx}: {ex}")
            e["validated"] = False
            e["validation_error"] = "exception"

    # write back file if changed
    if changed:
        write_real_scores(entries)
        _log(f"Updated real_scores.jsonl ({total_validated} validated, {total_triggered} trained).")
    else:
        _log("No changes made to real_scores.jsonl")

# ---------- Entrypoint ----------
if __name__ == "__main__":
    _log("ufa_auto_validate started")
    try:
        process_pending_entries()
    except Exception as e:
        _log(f"Fatal error in ufa_auto_validate: {e}")
    _log("ufa_auto_validate finished")
