"""
UFA v3 - PyTorch implementation for Emergent
Single-file module that provides:
- dataset loader from JSONL (training_set.jsonl / real_scores.jsonl)
- UFAv3 model (embeddings + MLP)
- train / eval / predict CLI
- save / load model + metadata
- helper to be called by existing scheduler (auto_retrain integration)

Paths (customize at top):
- DATA_DIR = '/app/data'
- MODELS_DIR = '/app/models'
- MODEL_FILE = 'ufa_model_v3.pt'
- META_FILE = 'ufa_model_v3_meta.json'

Usage examples:
$ python3 ufa_v3_for_emergent.py --mode train --epochs 30
$ python3 ufa_v3_for_emergent.py --mode predict --home "PSG" --away "Marseille" --league "Ligue1" --home_coeff 1.3 --away_coeff 1.0

The model predicts a probability distribution over a fixed set of scorelines.
"""

import os
import json
import argparse
import random
import time
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# --------------------------- Configuration ---------------------------
DATA_DIR = '/app/data'
MODELS_DIR = '/app/models'
MODEL_FILE = 'ufa_model_v3.pt'
META_FILE = 'ufa_model_v3_meta.json'

TRAINING_SET = os.path.join(DATA_DIR, 'training_set.jsonl')
# Fallbacks
PREDICTED_MATCHES = os.path.join(DATA_DIR, 'predicted_matches.jsonl')
REAL_SCORES = os.path.join(DATA_DIR, 'real_scores.jsonl')

# Device
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Score list: common scorelines to predict. Expand if needed.
SCORES = [
    '0-0','1-0','0-1','1-1','2-0','0-2','2-1','1-2','3-0','0-3',
    '2-2','3-1','1-3','3-2','2-3','4-0','0-4','4-1','1-4','4-2',
    '2-4','3-3','4-3','3-4','5-0'
]
SCORE_TO_IDX = {s:i for i,s in enumerate(SCORES)}
NUM_SCORES = len(SCORES)

# --------------------------- Utilities ---------------------------

def ensure_dirs():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)


def read_jsonl(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def save_meta(meta: dict):
    with open(os.path.join(MODELS_DIR, META_FILE), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_meta() -> dict:
    path = os.path.join(MODELS_DIR, META_FILE)
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --------------------------- Dataset ---------------------------
class UFADataset(Dataset):
    def __init__(self, records: List[dict], team2idx: Dict[str,int], league2idx: Dict[str,int], max_history: int = 5):
        self.records = records
        self.team2idx = team2idx
        self.league2idx = league2idx
        self.max_history = max_history

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        r = self.records[idx]
        # required fields (best-effort): home_team, away_team, league, home_coeff, away_coeff, real_score
        home = r.get('home_team') or r.get('home') or 'UNK_HOME'
        away = r.get('away_team') or r.get('away') or 'UNK_AWAY'
        league = r.get('league') or 'UNK_LEAGUE'
        home_coeff = float(r.get('home_coeff', r.get('home_rating', 1.0)))
        away_coeff = float(r.get('away_coeff', r.get('away_rating', 1.0)))

        home_idx = self.team2idx.get(home, self.team2idx.get('UNK_TEAM',0))
        away_idx = self.team2idx.get(away, self.team2idx.get('UNK_TEAM',1))
        league_idx = self.league2idx.get(league, self.league2idx.get('UNK_LEAGUE',0))

        # feature vector
        features = {
            'home_idx': home_idx,
            'away_idx': away_idx,
            'league_idx': league_idx,
            'home_coeff': home_coeff,
            'away_coeff': away_coeff
        }

        # label
        real = r.get('real_score') or r.get('score') or None
        label = -1
        if real:
            # normalize form "2-1"
            real = str(real).strip()
            if real in SCORE_TO_IDX:
                label = SCORE_TO_IDX[real]
            else:
                # try to parse numbers
                try:
                    parts = real.split('-')
                    sc = f"{int(parts[0])}-{int(parts[1])}"
                    if sc in SCORE_TO_IDX:
                        label = SCORE_TO_IDX[sc]
                except Exception:
                    label = -1
        return features, label

# collate
def collate_batch(batch):
    feats = batch
    home_idx = torch.tensor([f[0]['home_idx'] for f in batch], dtype=torch.long)
    away_idx = torch.tensor([f[0]['away_idx'] for f in batch], dtype=torch.long)
    league_idx = torch.tensor([f[0]['league_idx'] for f in batch], dtype=torch.long)
    coeffs = torch.tensor([[f[0]['home_coeff'], f[0]['away_coeff']] for f in batch], dtype=torch.float)
    labels = torch.tensor([f[1] for f in batch], dtype=torch.long)
    return {'home_idx': home_idx, 'away_idx': away_idx, 'league_idx': league_idx, 'coeffs': coeffs, 'labels': labels}

# --------------------------- Model ---------------------------
class UFAv3(nn.Module):
    def __init__(self, n_teams: int, n_leagues: int, emb_dim: int = 32, hidden: int = 128, dropout: float = 0.2):
        super().__init__()
        self.team_emb = nn.Embedding(n_teams, emb_dim)
        self.league_emb = nn.Embedding(n_leagues, max(8, emb_dim//2))
        self.fc_in = nn.Linear(emb_dim*2 + max(8, emb_dim//2) + 2, hidden)
        self.act = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc_mid = nn.Linear(hidden, hidden//2)
        self.fc_out = nn.Linear(hidden//2, NUM_SCORES)

    def forward(self, home_idx, away_idx, league_idx, coeffs):
        h = self.team_emb(home_idx)
        a = self.team_emb(away_idx)
        l = self.league_emb(league_idx)
        x = torch.cat([h, a, l, coeffs], dim=1)
        x = self.act(self.fc_in(x))
        x = self.dropout(x)
        x = self.act(self.fc_mid(x))
        logits = self.fc_out(x)
        return logits

# --------------------------- Helpers ---------------------------

def build_mappings(records: List[dict], min_occ: int = 1) -> Tuple[Dict[str,int], Dict[str,int]]:
    teams = Counter()
    leagues = Counter()
    for r in records:
        teams.update([r.get('home_team') or r.get('home') or 'UNK_TEAM'])
        teams.update([r.get('away_team') or r.get('away') or 'UNK_TEAM'])
        leagues.update([r.get('league') or 'UNK_LEAGUE'])
    team_list = ['UNK_TEAM'] + [t for t,c in teams.items() if c>=min_occ and t!='UNK_TEAM']
    league_list = ['UNK_LEAGUE'] + [l for l,c in leagues.items() if c>=min_occ and l!='UNK_LEAGUE']
    team2idx = {t:i for i,t in enumerate(team_list)}
    league2idx = {l:i for i,l in enumerate(league_list)}
    return team2idx, league2idx

# --------------------------- Training / Eval / Predict ---------------------------

def train_model(epochs: int = 20, batch_size: int = 64, lr: float = 1e-3, weight_decay: float = 1e-5, debug: bool = False):
    ensure_dirs()
    records = read_jsonl(TRAINING_SET)
    if not records:
        print('No training records found at', TRAINING_SET)
        return

    # build mappings from records
    team2idx, league2idx = build_mappings(records)
    meta = {'team2idx': team2idx, 'league2idx': league2idx}
    save_meta(meta)

    dataset = UFADataset(records, team2idx, league2idx)
    # split train/val
    random.shuffle(records)
    n = len(records)
    n_val = max(1, int(0.1*n))
    train_records = records[n_val:]
    val_records = records[:n_val]
    train_ds = UFADataset(train_records, team2idx, league2idx)
    val_ds = UFADataset(val_records, team2idx, league2idx)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_batch)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_batch)

    model = UFAv3(n_teams=len(team2idx), n_leagues=len(league2idx)).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.CrossEntropyLoss(ignore_index=-1)

    best_val = 1e9
    for epoch in range(1, epochs+1):
        model.train()
        total_loss = 0.0
        total = 0
        for batch in train_loader:
            home_idx = batch['home_idx'].to(DEVICE)
            away_idx = batch['away_idx'].to(DEVICE)
            league_idx = batch['league_idx'].to(DEVICE)
            coeffs = batch['coeffs'].to(DEVICE)
            labels = batch['labels'].to(DEVICE)

            # filter valid labels
            mask = labels >= 0
            if mask.sum().item() == 0:
                continue
            logits = model(home_idx, away_idx, league_idx, coeffs)
            loss = criterion(logits[mask], labels[mask])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item() * mask.sum().item()
            total += mask.sum().item()

        avg_loss = total_loss / max(1, total)

        # validation
        model.eval()
        val_loss = 0.0
        val_total = 0
        correct = 0
        with torch.no_grad():
            for batch in val_loader:
                home_idx = batch['home_idx'].to(DEVICE)
                away_idx = batch['away_idx'].to(DEVICE)
                league_idx = batch['league_idx'].to(DEVICE)
                coeffs = batch['coeffs'].to(DEVICE)
                labels = batch['labels'].to(DEVICE)
                mask = labels >= 0
                if mask.sum().item() == 0:
                    continue
                logits = model(home_idx, away_idx, league_idx, coeffs)
                loss = criterion(logits[mask], labels[mask])
                val_loss += loss.item() * mask.sum().item()
                val_total += mask.sum().item()
                preds = logits.argmax(dim=1)
                correct += (preds[mask]==labels[mask]).sum().item()
        avg_val_loss = val_loss / max(1, val_total)
        acc = correct / max(1, val_total)

        print(f"Epoch {epoch}/{epochs}  train_loss={avg_loss:.4f}  val_loss={avg_val_loss:.4f}  val_acc={acc:.4f}")

        # save best
        if avg_val_loss < best_val:
            best_val = avg_val_loss
            best_acc = acc
            torch.save(model.state_dict(), os.path.join(MODELS_DIR, MODEL_FILE))
            save_meta({'team2idx': team2idx, 'league2idx': league2idx})
            print('Saved best model')

    # Enregistrer performance dans l'historique
    try:
        perf_history_path = "/app/logs/performance_history.jsonl"
        perf_record = {
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "accuracy": round(best_acc * 100, 2) if 'best_acc' in locals() else 0.0
        }
        with open(perf_history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(perf_record) + "\n")
        print(f"Performance enregistrée: {perf_record['accuracy']}%")
    except Exception as e:
        print(f"Erreur enregistrement performance: {e}")
    
    print('Training finished')


def evaluate_on_dataset(path: str, batch_size: int = 128):
    records = read_jsonl(path)
    if not records:
        print('No records to evaluate at', path)
        return
    meta = load_meta()
    team2idx = meta.get('team2idx', {})
    league2idx = meta.get('league2idx', {})
    ds = UFADataset(records, team2idx, league2idx)
    loader = DataLoader(ds, batch_size=batch_size, collate_fn=collate_batch)

    model = UFAv3(n_teams=max(2, len(team2idx)), n_leagues=max(1, len(league2idx))).to(DEVICE)
    model_path = os.path.join(MODELS_DIR, MODEL_FILE)
    if not os.path.exists(model_path):
        print('No model found at', model_path)
        return
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.eval()

    total = 0
    correct = 0
    with torch.no_grad():
        for batch in loader:
            home_idx = batch['home_idx'].to(DEVICE)
            away_idx = batch['away_idx'].to(DEVICE)
            league_idx = batch['league_idx'].to(DEVICE)
            coeffs = batch['coeffs'].to(DEVICE)
            labels = batch['labels'].to(DEVICE)
            mask = labels >= 0
            if mask.sum().item() == 0:
                continue
            logits = model(home_idx, away_idx, league_idx, coeffs)
            preds = logits.argmax(dim=1)
            correct += (preds[mask]==labels[mask]).sum().item()
            total += mask.sum().item()
    print(f'Eval accuracy: {correct}/{total} = {correct/total:.4f}')


def predict_single(home: str, away: str, league: str, home_coeff: float, away_coeff: float, topk: int = 10) -> List[Tuple[str,float]]:
    meta = load_meta()
    team2idx = meta.get('team2idx', {})
    league2idx = meta.get('league2idx', {})
    home_idx = team2idx.get(home, team2idx.get('UNK_TEAM', 0))
    away_idx = team2idx.get(away, team2idx.get('UNK_TEAM', 1))
    league_idx = league2idx.get(league, league2idx.get('UNK_LEAGUE', 0))

    model = UFAv3(n_teams=max(2, len(team2idx)), n_leagues=max(1, len(league2idx))).to(DEVICE)
    model_path = os.path.join(MODELS_DIR, MODEL_FILE)
    if not os.path.exists(model_path):
        raise FileNotFoundError('Model not found. Please train first.')
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.eval()

    tensor_home = torch.tensor([home_idx], dtype=torch.long).to(DEVICE)
    tensor_away = torch.tensor([away_idx], dtype=torch.long).to(DEVICE)
    tensor_league = torch.tensor([league_idx], dtype=torch.long).to(DEVICE)
    tensor_coeffs = torch.tensor([[home_coeff, away_coeff]], dtype=torch.float).to(DEVICE)

    with torch.no_grad():
        logits = model(tensor_home, tensor_away, tensor_league, tensor_coeffs)
        probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()

    scored = [(SCORES[i], float(probs[i])) for i in range(len(probs))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:topk]

# --------------------------- Integration Helper ---------------------------

def auto_retrain(epochs: int = 10):
    """Integration point for your scheduler. This function will:
    - Load training_set.jsonl (assumed prepared by existing pipeline)
    - Train ufa v3 and save model
    - Optionally evaluate on recent matches
    """
    print('Auto retrain started')
    train_model(epochs=epochs)
    # Optionally evaluate on a held-out set or real_scores
    if os.path.exists(REAL_SCORES):
        print('Evaluating on real scores...')
        evaluate_on_dataset(REAL_SCORES)
    print('Auto retrain finished')

# --------------------------- Incremental Training + Wallcap ---------------------------

def save_checkpoint(model, path_tmp):
    torch.save(model.state_dict(), path_tmp)


def train_model_incremental(train_path: str, epochs: int = 5, batch_size: int = 64, lr: float = 1e-4, weight_decay: float = 1e-6, wallcap_seconds: int = 3600, patience: int = 3):
    """Fine-tune existing model (if present) on train_path (jsonl of new records).
    Behavior:
    - Load existing meta and model if available
    - Build mappings; if new teams/leagues appear, extend embeddings by rebuilding model
    - Train with early stopping and wall-clock cap
    - Checkpoint each epoch and on time limit
    - Atomic replace at finish
    """
    ensure_dirs()
    records = read_jsonl(train_path)
    if not records:
        print('[INCREMENTAL] No records found for incremental training at', train_path)
        return

    meta = load_meta()
    saved_team2idx = meta.get('team2idx', {})
    saved_league2idx = meta.get('league2idx', {})

    # Build full mappings including new teams/leagues
    all_records = read_jsonl(TRAINING_SET)
    combined = all_records + records
    team2idx, league2idx = build_mappings(combined)

    # Save meta (will be used by predict)
    save_meta({'team2idx': team2idx, 'league2idx': league2idx})

    # Create dataset
    ds = UFADataset(combined, team2idx, league2idx)
    # Simple split
    random.shuffle(combined)
    n = len(combined)
    n_val = max(1, int(0.05 * n))
    train_records = combined[n_val:]
    val_records = combined[:n_val]
    train_ds = UFADataset(train_records, team2idx, league2idx)
    val_ds = UFADataset(val_records, team2idx, league2idx)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_batch)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_batch)

    model = UFAv3(n_teams=len(team2idx), n_leagues=len(league2idx)).to(DEVICE)

    model_path = os.path.join(MODELS_DIR, MODEL_FILE)
    tmp_model_path = model_path + '.tmp'

    # If existing model exists, try to load weights (best-effort)
    if os.path.exists(model_path):
        try:
            model.load_state_dict(torch.load(model_path, map_location=DEVICE))
            print('[INCREMENTAL] Loaded existing model weights')
        except Exception as e:
            print('[INCREMENTAL] Warning: could not load existing weights:', e)

    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.CrossEntropyLoss(ignore_index=-1)

    best_val = 1e9
    best_epoch = -1
    no_improve = 0
    start_time = time.time()

    for epoch in range(1, epochs+1):
        model.train()
        total_loss = 0.0
        total = 0
        for batch in train_loader:
            home_idx = batch['home_idx'].to(DEVICE)
            away_idx = batch['away_idx'].to(DEVICE)
            league_idx = batch['league_idx'].to(DEVICE)
            coeffs = batch['coeffs'].to(DEVICE)
            labels = batch['labels'].to(DEVICE)

            mask = labels >= 0
            if mask.sum().item() == 0:
                continue
            logits = model(home_idx, away_idx, league_idx, coeffs)
            loss = criterion(logits[mask], labels[mask])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item() * mask.sum().item()
            total += mask.sum().item()

            # wallcap check inside training loop to be responsive
            if time.time() - start_time > wallcap_seconds:
                print('[INCREMENTAL] Wallcap reached during training loop.')
                break

        avg_loss = total_loss / max(1, total)

        # Validation
        model.eval()
        val_loss = 0.0
        val_total = 0
        correct = 0
        with torch.no_grad():
            for batch in val_loader:
                home_idx = batch['home_idx'].to(DEVICE)
                away_idx = batch['away_idx'].to(DEVICE)
                league_idx = batch['league_idx'].to(DEVICE)
                coeffs = batch['coeffs'].to(DEVICE)
                labels = batch['labels'].to(DEVICE)
                mask = labels >= 0
                if mask.sum().item() == 0:
                    continue
                logits = model(home_idx, away_idx, league_idx, coeffs)
                loss = criterion(logits[mask], labels[mask])
                val_loss += loss.item() * mask.sum().item()
                val_total += mask.sum().item()
                preds = logits.argmax(dim=1)
                correct += (preds[mask]==labels[mask]).sum().item()
        avg_val_loss = val_loss / max(1, val_total)
        acc = correct / max(1, val_total) if val_total>0 else 0.0

        print(f"[INCREMENTAL] Epoch {epoch}/{epochs} train_loss={avg_loss:.4f} val_loss={avg_val_loss:.4f} val_acc={acc:.4f}")

        # checkpoint
        try:
            save_checkpoint(model, tmp_model_path)
        except Exception as e:
            print('[INCREMENTAL] Warning: checkpoint failed:', e)

        # early stopping
        if avg_val_loss < best_val:
            best_val = avg_val_loss
            best_epoch = epoch
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= patience:
            print('[INCREMENTAL] Early stopping triggered')
            break

        if time.time() - start_time > wallcap_seconds:
            print('[INCREMENTAL] Wallcap reached after epoch actions')
            break

    # Finalize: atomic replace if tmp exists
    final_tmp = tmp_model_path
    if os.path.exists(final_tmp):
        try:
            os.replace(final_tmp, model_path)
            print('[INCREMENTAL] Model saved atomically to', model_path)
        except Exception as e:
            print('[INCREMENTAL] Error saving final model:', e)
    else:
        print('[INCREMENTAL] No checkpoint found to save')

# --------------------------- CLI ---------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, choices=['train','predict','eval','auto_retrain'], default='train')
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--home', type=str, help='home team name for predict')
    parser.add_argument('--away', type=str, help='away team name for predict')
    parser.add_argument('--league', type=str, default='UNK_LEAGUE')
    parser.add_argument('--home_coeff', type=float, default=1.0)
    parser.add_argument('--away_coeff', type=float, default=1.0)
    parser.add_argument('--topk', type=int, default=10)
    args = parser.parse_args()

    if args.mode == 'train':
        train_model(epochs=args.epochs, batch_size=args.batch_size)
    elif args.mode == 'eval':
        evaluate_on_dataset(REAL_SCORES)
    elif args.mode == 'auto_retrain':
        auto_retrain(epochs=args.epochs)
    elif args.mode == 'predict':
        if not args.home or not args.away:
            print('Please provide --home and --away for prediction')
            return
        res = predict_single(args.home, args.away, args.league, args.home_coeff, args.away_coeff, topk=args.topk)
        print('Top predictions:')
        for s,p in res:
            print(f"{s} -> {p:.4f}")

if __name__ == '__main__':
    main()
