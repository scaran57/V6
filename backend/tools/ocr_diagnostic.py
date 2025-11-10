#!/usr/bin/env python3
# /app/backend/tools/ocr_diagnostic.py
"""
Diagnostic OCR complet pour Emergent.
Usage:
  python3 ocr_diagnostic.py --input_dir /path/to/screenshots --out_dir /app/logs/ocr_diagnostics --team_map /app/data/team_map.json
"""
import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
import shutil
import re
import cv2
import numpy as np
import pytesseract
from fuzzywuzzy import process, fuzz

# --- CONFIG ---
TESS_LANG = "fra+eng"   # langues à utiliser
TESS_OEM = 1            # LSTM
# psm candidates used below
SCORE_REGEX = re.compile(r"(\b\d{1,2}\s*[-:]\s*\d{1,2}\b)")  # matches 1-0  10-2  etc.
ODDS_REGEX = re.compile(r"(\b\d{1,3}(?:[.,]\d+)?\b)")        # numbers / odds
STOPWORDS = set([
    "paris", "paris sur mesure", "stats", "compos", "match", "score exact", "voir",
    "s'inscrire", "connexion", "se connecter", "home", "away", "aucun", "choisir"
])
# Preprocessing variants to test
VARIANTS = [
    "orig",
    "resize_2x",
    "gray",
    "binar_otsu",
    "adaptive",
    "sharpen",
    "denoise",
    "morph_open"
]
# whitelist for score/odd extraction (characters likely in scores)
SCORE_WHITELIST = "0123456789-:"

# --- helpers ---
def ensure_dir(p:Path):
    p.mkdir(parents=True, exist_ok=True)

def read_team_map(path):
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_img(path, img):
    cv2.imwrite(str(path), img)

def ocr_image(img, psm=6, oem=TESS_OEM, lang=TESS_LANG, whitelist=None):
    config = f"--oem {oem} --psm {psm}"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"
    text = pytesseract.image_to_string(img, lang=lang, config=config)
    return text

def clean_text_for_team_detection(text):
    # Remove common UI words, punctuation
    t = text.lower()
    for w in STOPWORDS:
        t = t.replace(w, " ")
    t = re.sub(r"[^a-z0-9éèàçùôâî\-:\/\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def find_scores(tex):
    scores = SCORE_REGEX.findall(tex)
    # normalize (remove spaces)
    return [s.replace(" ", "").replace(":", "-") for s in scores]

def best_team_match(name_candidate, team_map, limit=3):
    # team_map expected: {"Real Madrid": "LaLiga", ...}
    names = list(team_map.keys())
    if not names:
        return None, 0
    best = process.extractOne(name_candidate, names, scorer=fuzz.token_sort_ratio)
    if best:
        return best[0], best[1]  # name, score 0-100
    return None, 0

# --- preprocessing functions ---
def preprocess_variant(img, variant):
    h, w = img.shape[:2]
    if variant == "orig":
        return img
    if variant == "resize_2x":
        return cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
    if variant == "gray":
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if variant == "binar_otsu":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5,5), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return th
    if variant == "adaptive":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        th = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY,11,2)
        return th
    if variant == "sharpen":
        kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        return cv2.filter2D(img, -1, kernel)
    if variant == "denoise":
        return cv2.fastNlMeansDenoisingColored(img,None,10,10,7,21)
    if variant == "morph_open":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        kernel = np.ones((3,3),np.uint8)
        opened = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
        return opened
    return img

# --- main diagnostic run ---
def analyze_folder(input_dir, out_dir, team_map_path=None, max_files=200):
    input_dir = Path(input_dir)
    out_dir = Path(out_dir)
    ensure_dir(out_dir)
    img_out = out_dir / "preprocessed_images"
    ensure_dir(img_out)
    ensure_dir(out_dir / "raw_texts")
    ensure_dir(out_dir / "reports")
    ensure_dir(out_dir / "variants")

    team_map = read_team_map(team_map_path) if team_map_path else {}
    files = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in [".jpg",".jpeg",".png"]])
    files = files[:max_files]

    summary = {
        "run_time": datetime.utcnow().isoformat()+"Z",
        "total_files": len(files),
        "variant_stats": {v: {"files":0, "scores_found":0, "teams_found":0} for v in VARIANTS},
        "files": []
    }

    for i, f in enumerate(files, start=1):
        try:
            orig_img = cv2.imread(str(f))
            if orig_img is None:
                print(f"⚠️ Skip (can't read) {f}")
                continue
            file_entry = {
                "file": str(f.name),
                "variants": {}
            }

            for v in VARIANTS:
                proc = preprocess_variant(orig_img.copy(), v)
                # save small preview
                v_fn = img_out / f"{f.stem}_{v}.jpg"
                save_img(v_fn, proc)

                # Choose two psm modes to try for each variant (block + singleline)
                texts = {}
                for psm in (6, 7):  # 6 = assume a block of text, 7 = single text line
                    try:
                        # for psm=7 -> whitelist for scores (if image likely contains scores)
                        whitelist = None
                        txt = ocr_image(proc, psm=psm, whitelist=whitelist)
                        texts[f"psm{psm}"] = txt
                    except Exception as e:
                        texts[f"psm{psm}"] = f"OCR error: {e}"

                # combine texts
                combined_text = "\n".join([texts.get(k,"") for k in sorted(texts.keys())])
                cleaned = clean_text_for_team_detection(combined_text)
                scores = find_scores(combined_text)
                # attempt basic team split heuristic (look for "team - team" or "team vs team")
                home = away = None
                # search lines for separators
                lines = [ln.strip() for ln in combined_text.splitlines() if ln.strip()]
                for ln in lines[:8]:  # look in top lines first
                    if " - " in ln or " vs " in ln or "-" in ln:
                        # naive split
                        parts = re.split(r"\s+[-–—]\s+|\s+vs\s+|\s+VS\s+", ln)
                        if len(parts) >= 2:
                            home_cand = parts[0].strip()
                            away_cand = parts[1].strip()
                            home = home_cand
                            away = away_cand
                            break
                # fallback: try to extract from cleaned text tokens
                if not home or not away:
                    tokens = cleaned.splitlines() if "\n" in cleaned else cleaned.split("  ")
                    token_line = cleaned[:200]
                    # use fuzzy search on token substrings
                    best_home, best_home_score = best_team_match(token_line, team_map) if token_line else (None,0)
                    if best_home_score > 70:
                        home = best_home
                # fuzzy match each candidate to team_map if present
                home_match = {"name": None, "score": 0}
                away_match = {"name": None, "score": 0}
                if home:
                    hm, sc = best_team_match(home, team_map)
                    home_match = {"name": hm, "score": sc}
                if away:
                    am, sc2 = best_team_match(away, team_map)
                    away_match = {"name": am, "score": sc2}

                file_entry["variants"][v] = {
                    "ocr_text": combined_text,
                    "cleaned_text": cleaned,
                    "scores_found": scores,
                    "home_candidate_raw": home,
                    "away_candidate_raw": away,
                    "home_match": home_match,
                    "away_match": away_match,
                    "texts": texts
                }

                # update stats
                summary["variant_stats"][v]["files"] += 1
                if scores:
                    summary["variant_stats"][v]["scores_found"] += 1
                if home_match["name"] and away_match["name"]:
                    summary["variant_stats"][v]["teams_found"] += 1

            summary["files"].append(file_entry)

            # save per-file JSON
            with open(out_dir / "reports" / f"{f.stem}_diagnostic.json", "w", encoding="utf-8") as jf:
                json.dump(file_entry, jf, ensure_ascii=False, indent=2)

            print(f"[{i}/{len(files)}] Analyzed {f.name}")

        except Exception as e:
            print(f"Error analyzing {f}: {e}")

    # write overall summary
    with open(out_dir / "ocr_diagnostics_report.json", "w", encoding="utf-8") as rf:
        json.dump(summary, rf, ensure_ascii=False, indent=2)

    print("✅ Diagnostic finished. Outputs in:", out_dir)
    return summary

# --- CLI ---
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input_dir", required=True, help="Folder with images to analyze")
    p.add_argument("--out_dir", required=True, help="Output folder for logs/reports")
    p.add_argument("--team_map", required=False, help="JSON file with team map (optional)", default=None)
    p.add_argument("--max_files", required=False, type=int, default=200)
    args = p.parse_args()
    analyze_folder(args.input_dir, args.out_dir, args.team_map, max_files=args.max_files)
