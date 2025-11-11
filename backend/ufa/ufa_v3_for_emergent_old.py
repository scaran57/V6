#!/usr/bin/env python3
# /app/backend/ufa/ufa_v3_for_emergent.py
"""
UFA v3 - Modèle PyTorch avec entraînement incrémental.

Architecture:
- Neural Network pour prédiction de scores
- Entraînement incrémental (fine-tuning)
- Time cap & early stopping
- Swap atomique du modèle
- Calibration des probabilités

Usage:
    # Entraînement
    python3 ufa_v3_for_emergent.py --mode train
    
    # Prédiction
    from ufa_v3_for_emergent import predict_single
    scores = predict_single("PSG", "Marseille", "Ligue1", 1.3, 1.0)
"""

import os
import sys
import json
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np
from collections import Counter

# Configuration
DATA_DIR = "/app/data"
MODELS_DIR = "/app/models"
LOGS_DIR = "/app/logs"

MODEL_PATH = os.path.join(MODELS_DIR, "ufa_model_v3.pt")
MODEL_TMP_PATH = os.path.join(MODELS_DIR, "ufa_model_v3.tmp.pt")
META_PATH = os.path.join(MODELS_DIR, "ufa_v3_meta.json")
TRAINING_SET = os.path.join(DATA_DIR, "training_set.jsonl")
LAST_RETRAIN_FILE = os.path.join(DATA_DIR, "last_retrain_v3.json")
TRAINING_LOG = os.path.join(LOGS_DIR, "ufa_v3_training.log")

# Hyperparamètres
MAX_HOME_GOALS = 7
MAX_AWAY_GOALS = 7
EMBEDDING_DIM = 32
HIDDEN_DIM = 128
DROPOUT = 0.3
LEARNING_RATE = 0.001
BATCH_SIZE = 64
MIN_EPOCHS = 3
MAX_EPOCHS = 30
PATIENCE = 3  # Early stopping
CHECKPOINT_EVERY_MIN = 10

# Créer dossiers nécessaires
Path(MODELS_DIR).mkdir(parents=True, exist_ok=True)
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)


def log(msg):
    """Log un message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    with open(TRAINING_LOG, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")
    print(log_msg)


def read_jsonl(path):
    """Charge un fichier JSONL."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_last_retrain():
    """Charge les infos du dernier réentraînement."""
    if not os.path.exists(LAST_RETRAIN_FILE):
        return {}
    with open(LAST_RETRAIN_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_last_retrain(info: dict):
    """Sauvegarde les infos du réentraînement."""
    with open(LAST_RETRAIN_FILE, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def load_meta():
    """Charge les métadonnées du modèle."""
    if not os.path.exists(META_PATH):
        return {
            "teams": {},
            "leagues": {},
            "version": "3.0",
            "last_trained": None,
            "total_samples": 0
        }
    with open(META_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_meta(meta: dict):
    """Sauvegarde les métadonnées."""
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# =============================================================================
# MODÈLE PYTORCH
# =============================================================================

class UFAScorePredictorV3(nn.Module):
    """
    Neural Network pour prédire les scores de matchs de football.
    
    Architecture:
    - Embedding des équipes et ligues
    - Couches fully connected
    - Output: probabilités pour chaque combinaison (home_goals, away_goals)
    """
    
    def __init__(self, num_teams, num_leagues, embedding_dim=EMBEDDING_DIM, hidden_dim=HIDDEN_DIM):
        super(UFAScorePredictorV3, self).__init__()
        
        # Embeddings
        self.team_embedding = nn.Embedding(num_teams, embedding_dim)
        self.league_embedding = nn.Embedding(num_leagues, embedding_dim)
        
        # Input features: team embeds (2x), league embed, coeffs (2)
        input_dim = embedding_dim * 3 + 2
        
        # Network
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.dropout1 = nn.Dropout(DROPOUT)
        
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.dropout2 = nn.Dropout(DROPOUT)
        
        # Output: probabilité pour chaque combinaison de scores
        output_dim = (MAX_HOME_GOALS + 1) * (MAX_AWAY_GOALS + 1)
        self.fc_out = nn.Linear(hidden_dim, output_dim)
        
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax(dim=1)
    
    def forward(self, home_idx, away_idx, league_idx, home_coeff, away_coeff):
        """
        Forward pass.
        
        Args:
            home_idx: Tensor [batch] - indices équipe domicile
            away_idx: Tensor [batch] - indices équipe extérieur
            league_idx: Tensor [batch] - indices ligue
            home_coeff: Tensor [batch] - coefficients domicile
            away_coeff: Tensor [batch] - coefficients extérieur
        
        Returns:
            Tensor [batch, num_outcomes] - probabilités
        """
        # Embeddings
        home_emb = self.team_embedding(home_idx)
        away_emb = self.team_embedding(away_idx)
        league_emb = self.league_embedding(league_idx)
        
        # Concatenate features
        x = torch.cat([
            home_emb,
            away_emb,
            league_emb,
            home_coeff.unsqueeze(1),
            away_coeff.unsqueeze(1)
        ], dim=1)
        
        # Forward
        x = self.fc1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.dropout1(x)
        
        x = self.fc2(x)
        x = self.bn2(x)
        x = self.relu(x)
        x = self.dropout2(x)
        
        x = self.fc_out(x)
        x = self.softmax(x)
        
        return x


# =============================================================================
# DATASET
# =============================================================================

class MatchDataset(Dataset):
    """Dataset pour les matchs."""
    
    def __init__(self, records, team_to_idx, league_to_idx):
        self.records = records
        self.team_to_idx = team_to_idx
        self.league_to_idx = league_to_idx
    
    def __len__(self):
        return len(self.records)
    
    def __getitem__(self, idx):
        record = self.records[idx]
        
        # Obtenir indices
        home_team = record.get("home_team", "Unknown")
        away_team = record.get("away_team", "Unknown")
        league = record.get("league", "Unknown")
        
        home_idx = self.team_to_idx.get(home_team, 0)
        away_idx = self.team_to_idx.get(away_team, 0)
        league_idx = self.league_to_idx.get(league, 0)
        
        # Coefficients
        home_coeff = float(record.get("home_coeff", 1.0))
        away_coeff = float(record.get("away_coeff", 1.0))
        
        # Score réel
        actual = record.get("actual", {})
        home_goals = actual.get("home_goals") or actual.get("home", 0)
        away_goals = actual.get("away_goals") or actual.get("away", 0)
        
        # Limiter aux max
        home_goals = min(int(home_goals), MAX_HOME_GOALS)
        away_goals = min(int(away_goals), MAX_AWAY_GOALS)
        
        # Convertir score en index de classe
        target = home_goals * (MAX_AWAY_GOALS + 1) + away_goals
        
        return {
            "home_idx": home_idx,
            "away_idx": away_idx,
            "league_idx": league_idx,
            "home_coeff": home_coeff,
            "away_coeff": away_coeff,
            "target": target
        }


# =============================================================================
# ENTRAÎNEMENT INCRÉMENTAL
# =============================================================================

def prepare_incremental_dataset():
    """
    Prépare le dataset incrémental (nouveaux matchs depuis dernier training).
    
    Returns:
        list: Nouveaux records
    """
    all_train = read_jsonl(TRAINING_SET)
    last = load_last_retrain()
    last_ts = last.get('timestamp')
    
    if not last_ts:
        # Premier run: utiliser tout
        log(f"📊 Premier entraînement: {len(all_train)} échantillons")
        return all_train
    
    last_dt = datetime.fromisoformat(last_ts)
    new = []
    
    for r in all_train:
        # Vérifier timestamp
        mt = r.get('match_time') or r.get('updated_at') or r.get('timestamp')
        if not mt:
            # Inclure par sécurité
            new.append(r)
            continue
        
        try:
            d = datetime.fromisoformat(mt)
            if d > last_dt:
                new.append(r)
        except:
            new.append(r)
    
    log(f"📊 Entraînement incrémental: {len(new)} nouveaux échantillons")
    return new


def build_vocabularies(records):
    """
    Construit les vocabulaires équipes et ligues.
    
    Returns:
        tuple: (team_to_idx, league_to_idx)
    """
    teams = set()
    leagues = set()
    
    for r in records:
        teams.add(r.get("home_team", "Unknown"))
        teams.add(r.get("away_team", "Unknown"))
        leagues.add(r.get("league", "Unknown"))
    
    team_to_idx = {t: i for i, t in enumerate(sorted(teams))}
    league_to_idx = {l: i for i, l in enumerate(sorted(leagues))}
    
    return team_to_idx, league_to_idx


def train_model_incremental(train_path: str, epochs: int, wallcap_seconds: int, batch_size: int = BATCH_SIZE):
    """
    Entraînement incrémental avec time cap et early stopping.
    
    Args:
        train_path: Chemin vers training data
        epochs: Nombre d'epochs
        wallcap_seconds: Limite de temps en secondes
        batch_size: Taille des batchs
    """
    log("=" * 70)
    log("🚀 ENTRAÎNEMENT INCRÉMENTAL UFA V3")
    log("=" * 70)
    
    start_time = time.time()
    
    # Charger données
    records = read_jsonl(train_path)
    if not records:
        log("❌ Aucune donnée d'entraînement")
        return
    
    log(f"📊 {len(records)} échantillons chargés")
    
    # Build vocabularies
    team_to_idx, league_to_idx = build_vocabularies(records)
    num_teams = len(team_to_idx)
    num_leagues = len(league_to_idx)
    
    log(f"📚 Vocabulaire: {num_teams} équipes, {num_leagues} ligues")
    
    # Split train/val
    val_size = max(1, int(len(records) * 0.1))
    train_records = records[:-val_size]
    val_records = records[-val_size:]
    
    log(f"📊 Train: {len(train_records)}, Val: {len(val_records)}")
    
    # Datasets
    train_dataset = MatchDataset(train_records, team_to_idx, league_to_idx)
    val_dataset = MatchDataset(val_records, team_to_idx, league_to_idx)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Modèle
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    log(f"💻 Device: {device}")
    
    # Charger modèle existant ou créer nouveau
    if os.path.exists(MODEL_PATH):
        log("📦 Chargement modèle existant pour fine-tuning")
        try:
            checkpoint = torch.load(MODEL_PATH, map_location=device)
            model = UFAScorePredictorV3(num_teams, num_leagues).to(device)
            model.load_state_dict(checkpoint['model_state_dict'])
            log("✅ Modèle chargé avec succès")
        except Exception as e:
            log(f"⚠️  Erreur chargement modèle: {e}, création nouveau modèle")
            model = UFAScorePredictorV3(num_teams, num_leagues).to(device)
    else:
        log("🆕 Création nouveau modèle")
        model = UFAScorePredictorV3(num_teams, num_leagues).to(device)
    
    # Optimizer & loss
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()
    
    # Early stopping
    best_val_loss = float('inf')
    patience_counter = 0
    last_checkpoint_time = time.time()
    
    log("=" * 70)
    log("🏋️  DÉBUT ENTRAÎNEMENT")
    log("=" * 70)
    
    for epoch in range(epochs):
        # Vérifier time cap
        elapsed = time.time() - start_time
        if elapsed > wallcap_seconds:
            log(f"⏰ Time cap atteint ({elapsed:.0f}s > {wallcap_seconds}s)")
            break
        
        # Training
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for batch in train_loader:
            home_idx = torch.tensor(batch['home_idx']).to(device)
            away_idx = torch.tensor(batch['away_idx']).to(device)
            league_idx = torch.tensor(batch['league_idx']).to(device)
            home_coeff = torch.tensor(batch['home_coeff'], dtype=torch.float32).to(device)
            away_coeff = torch.tensor(batch['away_coeff'], dtype=torch.float32).to(device)
            targets = torch.tensor(batch['target']).to(device)
            
            # Forward
            optimizer.zero_grad()
            outputs = model(home_idx, away_idx, league_idx, home_coeff, away_coeff)
            loss = criterion(outputs, targets)
            
            # Backward
            loss.backward()
            optimizer.step()
            
            # Stats
            train_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            train_correct += (predicted == targets).sum().item()
            train_total += targets.size(0)
        
        train_loss /= len(train_loader)
        train_acc = 100.0 * train_correct / train_total
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                home_idx = torch.tensor(batch['home_idx']).to(device)
                away_idx = torch.tensor(batch['away_idx']).to(device)
                league_idx = torch.tensor(batch['league_idx']).to(device)
                home_coeff = torch.tensor(batch['home_coeff'], dtype=torch.float32).to(device)
                away_coeff = torch.tensor(batch['away_coeff'], dtype=torch.float32).to(device)
                targets = torch.tensor(batch['target']).to(device)
                
                outputs = model(home_idx, away_idx, league_idx, home_coeff, away_coeff)
                loss = criterion(outputs, targets)
                
                val_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                val_correct += (predicted == targets).sum().item()
                val_total += targets.size(0)
        
        val_loss /= len(val_loader)
        val_acc = 100.0 * val_correct / val_total
        
        log(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f}, Acc: {train_acc:.2f}% | Val Loss: {val_loss:.4f}, Acc: {val_acc:.2f}%")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            
            # Sauvegarder meilleur modèle
            torch.save({
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'epoch': epoch,
                'val_loss': val_loss,
                'val_acc': val_acc,
                'team_to_idx': team_to_idx,
                'league_to_idx': league_to_idx
            }, MODEL_TMP_PATH)
            
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                log(f"⏸️  Early stopping (patience {PATIENCE})")
                break
        
        # Checkpoint périodique
        if time.time() - last_checkpoint_time > CHECKPOINT_EVERY_MIN * 60:
            torch.save({
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'epoch': epoch,
                'val_loss': val_loss,
                'val_acc': val_acc,
                'team_to_idx': team_to_idx,
                'league_to_idx': league_to_idx
            }, MODEL_TMP_PATH)
            log(f"💾 Checkpoint sauvegardé (epoch {epoch+1})")
            last_checkpoint_time = time.time()
    
    # Swap atomique
    if os.path.exists(MODEL_TMP_PATH):
        os.replace(MODEL_TMP_PATH, MODEL_PATH)
        log(f"✅ Modèle sauvegardé atomiquement: {MODEL_PATH}")
    
    # Sauvegarder métadonnées
    meta = {
        "version": "3.0",
        "last_trained": datetime.now(timezone.utc).isoformat(),
        "total_samples": len(records),
        "num_teams": num_teams,
        "num_leagues": num_leagues,
        "best_val_loss": best_val_loss,
        "best_val_acc": val_acc,
        "epochs_trained": epoch + 1,
        "team_to_idx": team_to_idx,
        "league_to_idx": league_to_idx
    }
    save_meta(meta)
    
    log("=" * 70)
    log("✅ ENTRAÎNEMENT TERMINÉ")
    log(f"📊 Best Val Loss: {best_val_loss:.4f}, Acc: {val_acc:.2f}%")
    log(f"⏱️  Durée: {time.time() - start_time:.1f}s")
    log("=" * 70)


def auto_retrain(max_walltime_minutes: int = 60, base_epochs: int = 10):
    """
    Réentraînement automatique incrémental.
    
    Args:
        max_walltime_minutes: Limite de temps en minutes
        base_epochs: Nombre d'epochs de base
    """
    log("=" * 70)
    log("🤖 AUTO-RETRAIN UFA V3")
    log("=" * 70)
    log(f"🕐 {datetime.now(timezone.utc).isoformat()}")
    
    # Préparer dataset incrémental
    new_records = prepare_incremental_dataset()
    num_new = len(new_records)
    
    if num_new == 0:
        log("⏳ Aucun nouveau record à entraîner")
        save_last_retrain({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'new_count': 0
        })
        return
    
    # Calculer epochs dynamiquement
    epochs = max(MIN_EPOCHS, min(MAX_EPOCHS, int(num_new / 50) + 1))
    log(f"📊 Nouveaux échantillons: {num_new}, Epochs: {epochs}")
    
    # Créer fichier temporaire d'entraînement
    temp_train_path = os.path.join(DATA_DIR, 'training_set_incremental.jsonl')
    with open(temp_train_path, 'w', encoding='utf-8') as f:
        for r in new_records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    
    wallcap = max_walltime_minutes * 60
    
    try:
        # Lancer entraînement
        train_model_incremental(
            train_path=temp_train_path,
            epochs=epochs,
            wallcap_seconds=wallcap,
            batch_size=BATCH_SIZE
        )
        
        # Mise à jour last_retrain
        save_last_retrain({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'new_count': num_new,
            'epochs': epochs
        })
        
        log("✅ Auto-retrain terminé avec succès")
        
    except Exception as e:
        log(f"❌ Erreur durant auto-retrain: {e}")
        import traceback
        log(traceback.format_exc())


# =============================================================================
# PRÉDICTION
# =============================================================================

def predict_single(home_team: str, away_team: str, league: str, 
                  home_coeff: float, away_coeff: float, topk: int = 10) -> List[Tuple[str, float]]:
    """
    Prédit les scores probables pour un match.
    
    Args:
        home_team: Équipe domicile
        away_team: Équipe extérieur
        league: Ligue
        home_coeff: Coefficient domicile
        away_coeff: Coefficient extérieur
        topk: Nombre de top scores à retourner
    
    Returns:
        List[(score, probability)]: Top K scores avec probabilités
    """
    # Charger modèle et meta
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Modèle UFA v3 non trouvé: {MODEL_PATH}")
    
    meta = load_meta()
    team_to_idx = meta.get('team_to_idx', {})
    league_to_idx = meta.get('league_to_idx', {})
    num_teams = meta.get('num_teams', len(team_to_idx))
    num_leagues = meta.get('num_leagues', len(league_to_idx))
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Charger modèle
    checkpoint = torch.load(MODEL_PATH, map_location=device)
    model = UFAScorePredictorV3(num_teams, num_leagues).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # Obtenir indices
    home_idx = team_to_idx.get(home_team, 0)
    away_idx = team_to_idx.get(away_team, 0)
    league_idx = league_to_idx.get(league, 0)
    
    # Préparer tensors
    home_idx_t = torch.tensor([home_idx]).to(device)
    away_idx_t = torch.tensor([away_idx]).to(device)
    league_idx_t = torch.tensor([league_idx]).to(device)
    home_coeff_t = torch.tensor([home_coeff], dtype=torch.float32).to(device)
    away_coeff_t = torch.tensor([away_coeff], dtype=torch.float32).to(device)
    
    # Prédiction
    with torch.no_grad():
        probs = model(home_idx_t, away_idx_t, league_idx_t, home_coeff_t, away_coeff_t)
        probs = probs.cpu().numpy()[0]
    
    # Convertir en liste de (score, prob)
    results = []
    for i, prob in enumerate(probs):
        home_goals = i // (MAX_AWAY_GOALS + 1)
        away_goals = i % (MAX_AWAY_GOALS + 1)
        score = f"{home_goals}-{away_goals}"
        results.append((score, float(prob)))
    
    # Trier par probabilité
    results.sort(key=lambda x: x[1], reverse=True)
    
    return results[:topk]


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="UFA v3 - PyTorch Model")
    parser.add_argument("--mode", choices=["train", "predict", "auto"], default="auto",
                       help="Mode: train (manuel), predict (test), auto (auto-retrain)")
    parser.add_argument("--home", type=str, help="Équipe domicile (mode predict)")
    parser.add_argument("--away", type=str, help="Équipe extérieur (mode predict)")
    parser.add_argument("--league", type=str, help="Ligue (mode predict)")
    parser.add_argument("--walltime", type=int, default=60, help="Time cap en minutes")
    
    args = parser.parse_args()
    
    if args.mode == "train":
        # Entraînement manuel sur training_set.jsonl complet
        if os.path.exists(TRAINING_SET):
            train_model_incremental(TRAINING_SET, MAX_EPOCHS, args.walltime * 60)
        else:
            print(f"❌ {TRAINING_SET} non trouvé")
    
    elif args.mode == "predict":
        if not all([args.home, args.away, args.league]):
            print("❌ --home, --away, --league requis pour mode predict")
            sys.exit(1)
        
        results = predict_single(args.home, args.away, args.league, 1.0, 1.0, topk=10)
        print(f"\n🎯 Prédictions {args.home} vs {args.away} ({args.league}):")
        print("-" * 50)
        for score, prob in results:
            print(f"{score:>6} : {prob*100:5.2f}%")
    
    elif args.mode == "auto":
        auto_retrain(max_walltime_minutes=args.walltime)
