#!/usr/bin/env python3
# /app/backend/ufa/ufa_v3_for_emergent.py
"""
UFA v3 - Modèle PyTorch avec entraînement incrémental robuste.

Architecture:
- Neural Network pour prédiction de scores
- Entraînement incrémental (fine-tuning) avec preservation du modèle précédent
- Time cap & early stopping robustes
- Swap atomique du modèle avec backup automatique
- Calibration des probabilités
- Performance tracking amélioré

Nouvelles fonctionnalités (version robuste):
- Wall-clock time caps pour limiter le temps d'entraînement
- Backup automatique avant chaque entraînement
- Rollback en cas d'échec
- Métriques de performance détaillées
- Gestion de l'état incrémental

Usage:
    # Entraînement complet
    python3 ufa_v3_for_emergent.py --mode train --max_time_minutes 30
    
    # Entraînement incrémental (fine-tuning)
    python3 ufa_v3_for_emergent.py --mode train --incremental --max_time_minutes 10
    
    # Évaluation
    python3 ufa_v3_for_emergent.py --mode eval
    
    # Prédiction
    from ufa_v3_for_emergent import predict_single
    scores = predict_single("PSG", "Marseille", "Ligue1", 1.3, 1.0)
"""

import os
import sys
import json
import time
import shutil
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np
from collections import Counter
import argparse

# Configuration
DATA_DIR = "/app/data"
MODELS_DIR = "/app/models"
LOGS_DIR = "/app/logs"
BACKUP_DIR = "/app/models/backups"

MODEL_PATH = os.path.join(MODELS_DIR, "ufa_model_v3.pt")
MODEL_TMP_PATH = os.path.join(MODELS_DIR, "ufa_model_v3.tmp.pt")
MODEL_BACKUP_PATH = os.path.join(BACKUP_DIR, "ufa_model_v3_backup.pt")
META_PATH = os.path.join(MODELS_DIR, "ufa_v3_meta.json")
META_BACKUP_PATH = os.path.join(BACKUP_DIR, "ufa_v3_meta_backup.json")
TRAINING_SET = os.path.join(DATA_DIR, "training_set.jsonl")
LAST_RETRAIN_FILE = os.path.join(DATA_DIR, "last_retrain_v3.json")
TRAINING_LOG = os.path.join(LOGS_DIR, "ufa_v3_training.log")
PERFORMANCE_LOG = os.path.join(LOGS_DIR, "ufa_v3_performance.jsonl")

# Hyperparamètres
MAX_HOME_GOALS = 7
MAX_AWAY_GOALS = 7
EMBEDDING_DIM = 32
HIDDEN_DIM = 128
DROPOUT = 0.3
LEARNING_RATE = 0.001
LEARNING_RATE_INCREMENTAL = 0.0001  # Learning rate plus faible pour fine-tuning
BATCH_SIZE = 64
MIN_EPOCHS = 3
MAX_EPOCHS = 30
PATIENCE = 5  # Early stopping patience augmentée
CHECKPOINT_EVERY_MIN = 10
DEFAULT_MAX_TIME_MINUTES = 30  # Temps maximum par défaut

# Créer dossiers nécessaires
Path(MODELS_DIR).mkdir(parents=True, exist_ok=True)
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)


def log(msg, level="INFO"):
    """Log un message avec niveau."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [{level}] {msg}"
    with open(TRAINING_LOG, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")
    print(log_msg)


def log_performance(metrics: dict):
    """Log les métriques de performance en JSONL."""
    metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(PERFORMANCE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(metrics, ensure_ascii=False) + "\n")


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
    try:
        with open(LAST_RETRAIN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Erreur lecture last_retrain: {e}", "WARNING")
        return {}


def save_last_retrain(info: dict):
    """Sauvegarde les infos du réentraînement de manière atomique."""
    tmp_file = LAST_RETRAIN_FILE + ".tmp"
    try:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        # Atomic rename
        os.replace(tmp_file, LAST_RETRAIN_FILE)
    except Exception as e:
        log(f"Erreur sauvegarde last_retrain: {e}", "ERROR")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


def load_meta():
    """Charge les métadonnées du modèle."""
    if not os.path.exists(META_PATH):
        return {
            "version": "3.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "training_history": [],
            "total_samples": 0,
            "leagues": [],
            "teams": [],
            "last_trained": None,
            "model_status": "untrained"
        }
    try:
        with open(META_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Erreur lecture meta: {e}", "WARNING")
        return load_meta()  # Retourne meta par défaut


def save_meta(meta: dict):
    """Sauvegarde les métadonnées de manière atomique."""
    tmp_file = META_PATH + ".tmp"
    try:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        # Atomic rename
        os.replace(tmp_file, META_PATH)
    except Exception as e:
        log(f"Erreur sauvegarde meta: {e}", "ERROR")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


def backup_model():
    """Crée un backup du modèle actuel avant entraînement."""
    try:
        if os.path.exists(MODEL_PATH):
            shutil.copy2(MODEL_PATH, MODEL_BACKUP_PATH)
            log(f"✅ Backup du modèle créé: {MODEL_BACKUP_PATH}")
        if os.path.exists(META_PATH):
            shutil.copy2(META_PATH, META_BACKUP_PATH)
            log(f"✅ Backup des métadonnées créé: {META_BACKUP_PATH}")
        return True
    except Exception as e:
        log(f"❌ Erreur création backup: {e}", "ERROR")
        return False


def restore_backup():
    """Restaure le backup du modèle en cas d'échec."""
    try:
        if os.path.exists(MODEL_BACKUP_PATH):
            shutil.copy2(MODEL_BACKUP_PATH, MODEL_PATH)
            log(f"✅ Modèle restauré depuis backup")
        if os.path.exists(META_BACKUP_PATH):
            shutil.copy2(META_BACKUP_PATH, META_PATH)
            log(f"✅ Métadonnées restaurées depuis backup")
        return True
    except Exception as e:
        log(f"❌ Erreur restauration backup: {e}", "ERROR")
        return False


class ScoreDataset(Dataset):
    """Dataset pour l'entraînement du modèle."""
    
    def __init__(self, data: List[dict], team_vocab: Dict[str, int], league_vocab: Dict[str, int]):
        self.data = data
        self.team_vocab = team_vocab
        self.league_vocab = league_vocab
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        
        # Encoder les features
        home_team_idx = self.team_vocab.get(item.get("home_team", "UNK"), 0)
        away_team_idx = self.team_vocab.get(item.get("away_team", "UNK"), 0)
        league_idx = self.league_vocab.get(item.get("league", "Unknown"), 0)
        home_coeff = float(item.get("home_coeff", 1.0))
        away_coeff = float(item.get("away_coeff", 1.0))
        
        # Target: score réel
        home_score = int(item.get("home_score", 0))
        away_score = int(item.get("away_score", 0))
        
        # Clip pour éviter out of bounds
        home_score = min(home_score, MAX_HOME_GOALS)
        away_score = min(away_score, MAX_AWAY_GOALS)
        
        return {
            "home_team_idx": torch.tensor(home_team_idx, dtype=torch.long),
            "away_team_idx": torch.tensor(away_team_idx, dtype=torch.long),
            "league_idx": torch.tensor(league_idx, dtype=torch.long),
            "home_coeff": torch.tensor(home_coeff, dtype=torch.float32),
            "away_coeff": torch.tensor(away_coeff, dtype=torch.float32),
            "home_score": torch.tensor(home_score, dtype=torch.long),
            "away_score": torch.tensor(away_score, dtype=torch.long)
        }


class UFAModel(nn.Module):
    """Modèle de prédiction de scores."""
    
    def __init__(self, num_teams, num_leagues):
        super(UFAModel, self).__init__()
        
        # Embeddings
        self.team_embedding = nn.Embedding(num_teams, EMBEDDING_DIM, padding_idx=0)
        self.league_embedding = nn.Embedding(num_leagues, EMBEDDING_DIM, padding_idx=0)
        
        # MLP
        input_size = EMBEDDING_DIM * 3 + 2  # 3 embeddings + 2 coeffs
        self.fc1 = nn.Linear(input_size, HIDDEN_DIM)
        self.bn1 = nn.BatchNorm1d(HIDDEN_DIM)
        self.dropout1 = nn.Dropout(DROPOUT)
        
        self.fc2 = nn.Linear(HIDDEN_DIM, HIDDEN_DIM)
        self.bn2 = nn.BatchNorm1d(HIDDEN_DIM)
        self.dropout2 = nn.Dropout(DROPOUT)
        
        # Sorties séparées pour home et away
        self.home_output = nn.Linear(HIDDEN_DIM, MAX_HOME_GOALS + 1)
        self.away_output = nn.Linear(HIDDEN_DIM, MAX_AWAY_GOALS + 1)
        
        self.relu = nn.ReLU()
    
    def forward(self, home_team_idx, away_team_idx, league_idx, home_coeff, away_coeff):
        # Embeddings
        home_emb = self.team_embedding(home_team_idx)
        away_emb = self.team_embedding(away_team_idx)
        league_emb = self.league_embedding(league_idx)
        
        # Concat features
        coeffs = torch.stack([home_coeff, away_coeff], dim=1)
        x = torch.cat([home_emb, away_emb, league_emb, coeffs], dim=1)
        
        # MLP
        x = self.fc1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.dropout1(x)
        
        x = self.fc2(x)
        x = self.bn2(x)
        x = self.relu(x)
        x = self.dropout2(x)
        
        # Prédictions
        home_logits = self.home_output(x)
        away_logits = self.away_output(x)
        
        return home_logits, away_logits


def build_vocabularies(data: List[dict]) -> Tuple[Dict, Dict]:
    """Construit les vocabulaires équipes et ligues."""
    teams = set()
    leagues = set()
    
    for item in data:
        teams.add(item.get("home_team", "UNK"))
        teams.add(item.get("away_team", "UNK"))
        leagues.add(item.get("league", "Unknown"))
    
    # UNK/Unknown à l'index 0 (padding)
    team_vocab = {"UNK": 0}
    league_vocab = {"Unknown": 0}
    
    for idx, team in enumerate(sorted(teams), 1):
        if team not in team_vocab:
            team_vocab[team] = idx
    
    for idx, league in enumerate(sorted(leagues), 1):
        if league not in league_vocab:
            league_vocab[league] = idx
    
    return team_vocab, league_vocab


def train_model(incremental=False, max_time_minutes=DEFAULT_MAX_TIME_MINUTES):
    """
    Entraîne le modèle UFAv3.
    
    Args:
        incremental: Si True, charge le modèle existant et fait du fine-tuning
        max_time_minutes: Temps maximum d'entraînement en minutes
    """
    log(f"🚀 Début entraînement UFAv3 (incremental={incremental}, max_time={max_time_minutes}min)")
    start_time = time.time()
    max_time_seconds = max_time_minutes * 60
    
    # Backup du modèle existant
    if incremental and os.path.exists(MODEL_PATH):
        if not backup_model():
            log("❌ Impossible de créer backup, abandon entraînement", "ERROR")
            return False
    
    # Charger données
    data = read_jsonl(TRAINING_SET)
    if not data:
        log("❌ Aucune donnée d'entraînement disponible", "ERROR")
        return False
    
    log(f"📊 {len(data)} échantillons chargés")
    
    # Split train/val
    split_idx = int(len(data) * 0.85)
    train_data = data[:split_idx]
    val_data = data[split_idx:]
    
    log(f"📊 Train: {len(train_data)}, Val: {len(val_data)}")
    
    # Construire vocabulaires
    team_vocab, league_vocab = build_vocabularies(data)
    log(f"📖 Vocabulaires: {len(team_vocab)} équipes, {len(league_vocab)} ligues")
    
    # Datasets
    train_dataset = ScoreDataset(train_data, team_vocab, league_vocab)
    val_dataset = ScoreDataset(val_data, team_vocab, league_vocab)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # Modèle
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"🖥️  Device: {device}")
    
    model = UFAModel(len(team_vocab), len(league_vocab)).to(device)
    
    # Charger modèle existant si mode incrémental
    start_epoch = 0
    if incremental and os.path.exists(MODEL_PATH):
        try:
            checkpoint = torch.load(MODEL_PATH, map_location=device)
            model.load_state_dict(checkpoint["model_state"])
            start_epoch = checkpoint.get("epoch", 0)
            log(f"✅ Modèle existant chargé (epoch {start_epoch})")
        except Exception as e:
            log(f"⚠️  Impossible de charger modèle existant: {e}, entraînement from scratch", "WARNING")
            incremental = False
    
    # Optimizer avec learning rate adapté
    lr = LEARNING_RATE_INCREMENTAL if incremental else LEARNING_RATE
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    
    log(f"🎯 Learning rate: {lr}")
    
    # Training loop avec early stopping robuste
    best_val_loss = float('inf')
    patience_counter = 0
    best_model_state = None
    
    training_history = []
    
    for epoch in range(start_epoch, start_epoch + MAX_EPOCHS):
        # Vérifier time cap
        elapsed = time.time() - start_time
        if elapsed > max_time_seconds:
            log(f"⏰ Time cap atteint ({max_time_minutes}min), arrêt entraînement", "WARNING")
            break
        
        # Training phase
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for batch in train_loader:
            # Vérifier time cap dans la boucle
            if time.time() - start_time > max_time_seconds:
                log(f"⏰ Time cap atteint dans batch, arrêt", "WARNING")
                break
            
            home_team = batch["home_team_idx"].to(device)
            away_team = batch["away_team_idx"].to(device)
            league = batch["league_idx"].to(device)
            home_coeff = batch["home_coeff"].to(device)
            away_coeff = batch["away_coeff"].to(device)
            home_score_target = batch["home_score"].to(device)
            away_score_target = batch["away_score"].to(device)
            
            optimizer.zero_grad()
            
            home_logits, away_logits = model(home_team, away_team, league, home_coeff, away_coeff)
            
            loss_home = criterion(home_logits, home_score_target)
            loss_away = criterion(away_logits, away_score_target)
            loss = loss_home + loss_away
            
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            
            # Accuracy
            home_pred = home_logits.argmax(dim=1)
            away_pred = away_logits.argmax(dim=1)
            train_correct += ((home_pred == home_score_target) & (away_pred == away_score_target)).sum().item()
            train_total += home_team.size(0)
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                home_team = batch["home_team_idx"].to(device)
                away_team = batch["away_team_idx"].to(device)
                league = batch["league_idx"].to(device)
                home_coeff = batch["home_coeff"].to(device)
                away_coeff = batch["away_coeff"].to(device)
                home_score_target = batch["home_score"].to(device)
                away_score_target = batch["away_score"].to(device)
                
                home_logits, away_logits = model(home_team, away_team, league, home_coeff, away_coeff)
                
                loss_home = criterion(home_logits, home_score_target)
                loss_away = criterion(away_logits, away_score_target)
                loss = loss_home + loss_away
                
                val_loss += loss.item()
                
                home_pred = home_logits.argmax(dim=1)
                away_pred = away_logits.argmax(dim=1)
                val_correct += ((home_pred == home_score_target) & (away_pred == away_score_target)).sum().item()
                val_total += home_team.size(0)
        
        # Moyennes
        train_loss /= len(train_loader)
        val_loss /= len(val_loader)
        train_acc = 100.0 * train_correct / train_total if train_total > 0 else 0
        val_acc = 100.0 * val_correct / val_total if val_total > 0 else 0
        
        epoch_info = {
            "epoch": epoch + 1,
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4),
            "train_acc": round(train_acc, 2),
            "val_acc": round(val_acc, 2),
            "elapsed_min": round((time.time() - start_time) / 60, 2)
        }
        training_history.append(epoch_info)
        
        log(f"Epoch {epoch+1}/{start_epoch + MAX_EPOCHS}: "
            f"train_loss={train_loss:.4f}, val_loss={val_loss:.4f}, "
            f"train_acc={train_acc:.2f}%, val_acc={val_acc:.2f}%, "
            f"elapsed={epoch_info['elapsed_min']}min")
        
        # Early stopping avec meilleur modèle
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Sauvegarder le meilleur état
            best_model_state = {
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "epoch": epoch + 1,
                "val_loss": val_loss,
                "val_acc": val_acc,
                "team_vocab": team_vocab,
                "league_vocab": league_vocab
            }
            log(f"✅ Nouveau meilleur modèle (val_loss={val_loss:.4f})")
        else:
            patience_counter += 1
            log(f"⏳ Patience: {patience_counter}/{PATIENCE}")
            
            if patience_counter >= PATIENCE and epoch >= MIN_EPOCHS - 1:
                log(f"🛑 Early stopping déclenché (patience={PATIENCE})")
                break
    
    # Sauvegarder le meilleur modèle de manière atomique
    if best_model_state is None:
        log("❌ Aucun modèle valide entraîné", "ERROR")
        if incremental:
            log("🔄 Restauration du backup...", "WARNING")
            restore_backup()
        return False
    
    try:
        # Sauvegarde atomique
        torch.save(best_model_state, MODEL_TMP_PATH)
        os.replace(MODEL_TMP_PATH, MODEL_PATH)
        log(f"✅ Modèle sauvegardé: {MODEL_PATH}")
        
        # Mettre à jour métadonnées
        meta = load_meta()
        meta["last_trained"] = datetime.now(timezone.utc).isoformat()
        meta["total_samples"] = len(data)
        meta["leagues"] = list(league_vocab.keys())
        meta["teams"] = list(team_vocab.keys())
        meta["model_status"] = "trained"
        meta["training_mode"] = "incremental" if incremental else "full"
        meta["training_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epochs": len(training_history),
            "best_val_loss": round(best_val_loss, 4),
            "best_val_acc": round(best_model_state["val_acc"], 2),
            "samples": len(data),
            "duration_min": round((time.time() - start_time) / 60, 2),
            "mode": "incremental" if incremental else "full"
        })
        save_meta(meta)
        
        # Log performance
        log_performance({
            "event": "training_completed",
            "mode": "incremental" if incremental else "full",
            "epochs": len(training_history),
            "best_val_loss": best_val_loss,
            "best_val_acc": best_model_state["val_acc"],
            "duration_min": (time.time() - start_time) / 60,
            "samples": len(data)
        })
        
        log(f"✅ Entraînement terminé avec succès (durée: {(time.time() - start_time)/60:.2f}min)")
        return True
        
    except Exception as e:
        log(f"❌ Erreur sauvegarde modèle: {e}", "ERROR")
        if incremental:
            log("🔄 Restauration du backup...", "WARNING")
            restore_backup()
        return False


def evaluate_model():
    """Évalue le modèle sur l'ensemble de validation."""
    log("📊 Début évaluation du modèle")
    
    if not os.path.exists(MODEL_PATH):
        log("❌ Aucun modèle trouvé", "ERROR")
        return None
    
    # Charger données
    data = read_jsonl(TRAINING_SET)
    if not data:
        log("❌ Aucune donnée disponible", "ERROR")
        return None
    
    # Split
    split_idx = int(len(data) * 0.85)
    val_data = data[split_idx:]
    
    # Vocabulaires
    team_vocab, league_vocab = build_vocabularies(data)
    
    # Dataset
    val_dataset = ScoreDataset(val_data, team_vocab, league_vocab)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # Charger modèle
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = UFAModel(len(team_vocab), len(league_vocab)).to(device)
    
    checkpoint = torch.load(MODEL_PATH, map_location=device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    
    # Évaluation
    criterion = nn.CrossEntropyLoss()
    val_loss = 0.0
    val_correct = 0
    val_total = 0
    
    with torch.no_grad():
        for batch in val_loader:
            home_team = batch["home_team_idx"].to(device)
            away_team = batch["away_team_idx"].to(device)
            league = batch["league_idx"].to(device)
            home_coeff = batch["home_coeff"].to(device)
            away_coeff = batch["away_coeff"].to(device)
            home_score_target = batch["home_score"].to(device)
            away_score_target = batch["away_score"].to(device)
            
            home_logits, away_logits = model(home_team, away_team, league, home_coeff, away_coeff)
            
            loss_home = criterion(home_logits, home_score_target)
            loss_away = criterion(away_logits, away_score_target)
            loss = loss_home + loss_away
            
            val_loss += loss.item()
            
            home_pred = home_logits.argmax(dim=1)
            away_pred = away_logits.argmax(dim=1)
            val_correct += ((home_pred == home_score_target) & (away_pred == away_score_target)).sum().item()
            val_total += home_team.size(0)
    
    val_loss /= len(val_loader)
    val_acc = 100.0 * val_correct / val_total if val_total > 0 else 0
    
    results = {
        "val_loss": round(val_loss, 4),
        "val_acc": round(val_acc, 2),
        "val_samples": val_total
    }
    
    log(f"📊 Résultats évaluation: loss={val_loss:.4f}, acc={val_acc:.2f}%, samples={val_total}")
    
    return results


def predict_single(home_team: str, away_team: str, league: str, home_coeff: float, away_coeff: float) -> List[Dict]:
    """
    Prédit les probabilités de scores pour un match.
    
    Returns:
        Liste de dicts avec {home_score, away_score, probability}
    """
    if not os.path.exists(MODEL_PATH):
        log("❌ Modèle non trouvé, impossible de prédire", "ERROR")
        return []
    
    try:
        # Charger modèle
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(MODEL_PATH, map_location=device)
        
        team_vocab = checkpoint.get("team_vocab", {})
        league_vocab = checkpoint.get("league_vocab", {})
        
        model = UFAModel(len(team_vocab), len(league_vocab)).to(device)
        model.load_state_dict(checkpoint["model_state"])
        model.eval()
        
        # Encoder inputs
        home_idx = team_vocab.get(home_team, 0)
        away_idx = team_vocab.get(away_team, 0)
        league_idx = league_vocab.get(league, 0)
        
        home_team_tensor = torch.tensor([home_idx], dtype=torch.long).to(device)
        away_team_tensor = torch.tensor([away_idx], dtype=torch.long).to(device)
        league_tensor = torch.tensor([league_idx], dtype=torch.long).to(device)
        home_coeff_tensor = torch.tensor([home_coeff], dtype=torch.float32).to(device)
        away_coeff_tensor = torch.tensor([away_coeff], dtype=torch.float32).to(device)
        
        # Prédiction
        with torch.no_grad():
            home_logits, away_logits = model(
                home_team_tensor, away_team_tensor, league_tensor,
                home_coeff_tensor, away_coeff_tensor
            )
            
            home_probs = torch.softmax(home_logits, dim=1)[0].cpu().numpy()
            away_probs = torch.softmax(away_logits, dim=1)[0].cpu().numpy()
        
        # Calculer probabilités jointes
        predictions = []
        for h in range(len(home_probs)):
            for a in range(len(away_probs)):
                prob = float(home_probs[h] * away_probs[a])
                predictions.append({
                    "home_score": h,
                    "away_score": a,
                    "probability": prob
                })
        
        # Trier par probabilité décroissante
        predictions.sort(key=lambda x: x["probability"], reverse=True)
        
        # Normaliser
        total_prob = sum(p["probability"] for p in predictions)
        if total_prob > 0:
            for p in predictions:
                p["probability"] /= total_prob
        
        return predictions
        
    except Exception as e:
        log(f"❌ Erreur prédiction: {e}", "ERROR")
        return []


def get_model_status() -> dict:
    """Retourne le statut du modèle."""
    status = {
        "model_exists": os.path.exists(MODEL_PATH),
        "meta_exists": os.path.exists(META_PATH),
        "backup_exists": os.path.exists(MODEL_BACKUP_PATH)
    }
    
    if status["model_exists"]:
        status["model_size_mb"] = round(os.path.getsize(MODEL_PATH) / (1024 * 1024), 2)
    
    if status["meta_exists"]:
        meta = load_meta()
        status["version"] = meta.get("version")
        status["last_trained"] = meta.get("last_trained")
        status["total_samples"] = meta.get("total_samples")
        status["model_status"] = meta.get("model_status")
        status["num_teams"] = len(meta.get("teams", []))
        status["num_leagues"] = len(meta.get("leagues", []))
        status["training_history_count"] = len(meta.get("training_history", []))
    
    # Données disponibles
    if os.path.exists(TRAINING_SET):
        data = read_jsonl(TRAINING_SET)
        status["training_samples_available"] = len(data)
    
    return status


def main():
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="UFA v3 - Entraînement et prédiction")
    parser.add_argument("--mode", choices=["train", "eval", "status"], required=True,
                       help="Mode d'exécution")
    parser.add_argument("--incremental", action="store_true",
                       help="Mode entraînement incrémental (fine-tuning)")
    parser.add_argument("--max_time_minutes", type=int, default=DEFAULT_MAX_TIME_MINUTES,
                       help=f"Temps maximum d'entraînement en minutes (défaut: {DEFAULT_MAX_TIME_MINUTES})")
    
    args = parser.parse_args()
    
    if args.mode == "train":
        success = train_model(incremental=args.incremental, max_time_minutes=args.max_time_minutes)
        sys.exit(0 if success else 1)
    
    elif args.mode == "eval":
        results = evaluate_model()
        if results:
            print(json.dumps(results, indent=2))
            sys.exit(0)
        else:
            sys.exit(1)
    
    elif args.mode == "status":
        status = get_model_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        sys.exit(0)


if __name__ == "__main__":
    main()
