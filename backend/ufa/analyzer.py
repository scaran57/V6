"""
UFA Analyzer - Système d'analyse avec coefficients de ligue
Utilise les coefficients de position pour affiner les prédictions
"""
import json
import sys
from pathlib import Path
import numpy as np

# Import du système de prédiction existant
sys.path.insert(0, '/app/backend')
from score_predictor import calculate_probabilities

STATE_PATH = Path("/app/backend/ufa/training/state.json")

class UFAAnalyzer:
    """
    Analyseur UFA avec système de priors ajustables par ligue
    """
    
    def __init__(self):
        """Initialise l'analyseur avec les priors par défaut"""
        self.priors = {
            "draw_prior": 0.28,        # Probabilité de base pour un nul
            "avg_goals": 2.7,          # Moyenne de buts par match
            "home_advantage": 1.05,    # Avantage domicile
            "high_score_penalty": 0.75 # Pénalité pour scores élevés
        }
        
        # Charger l'état sauvegardé si disponible
        self.load_state()
    
    def load_state(self):
        """Charge l'état d'apprentissage précédent"""
        if STATE_PATH.exists():
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if "priors" in state:
                        self.priors.update(state["priors"])
                        print(f"[UFA Analyzer] État chargé depuis {STATE_PATH}")
            except Exception as e:
                print(f"[UFA Analyzer] Erreur chargement état: {e}")
    
    def predict_score_distribution(self, match_data, extracted_scores=None, diff_expected=1.0):
        """
        Prédit la distribution de probabilité des scores pour un match.
        
        Args:
            match_data: Données du match (home_team, away_team, league, etc.)
            extracted_scores: Cotes extraites du bookmaker
            diff_expected: Paramètre d'ajustement global
            
        Returns:
            Dict {score: probabilité}
        """
        if not extracted_scores:
            # Retourner une distribution par défaut si pas de cotes
            return self._default_distribution()
        
        # Utiliser le système de prédiction existant avec ajustements
        home_coef = match_data.get("home_coef", 1.0)
        away_coef = match_data.get("away_coef", 1.0)
        
        # Appliquer les priors UFA
        adjusted_diff = diff_expected * self.priors["avg_goals"] / 2.7
        
        # Calculer les probabilités avec le système existant
        probabilities = calculate_probabilities(
            extracted_scores,
            adjusted_diff,
            home_coef,
            away_coef
        )
        
        return probabilities
    
    def _default_distribution(self):
        """Distribution par défaut basée sur les priors"""
        return {
            "1-0": 0.12,
            "0-1": 0.11,
            "1-1": 0.18,
            "2-0": 0.09,
            "0-2": 0.08,
            "2-1": 0.15,
            "1-2": 0.14,
            "2-2": 0.09,
            "0-0": 0.04
        }
    
    def adjust_priors(self, league_losses):
        """
        Ajuste les priors selon la performance par ligue.
        
        Args:
            league_losses: Dict {league: average_loss}
            
        Returns:
            Dict des nouveaux priors
        """
        # Calculer la perte moyenne globale
        if not league_losses:
            return self.priors
        
        avg_loss = np.mean(list(league_losses.values()))
        
        # Ajuster avg_goals selon la performance
        if avg_loss > 2.5:  # Performance faible
            self.priors["avg_goals"] *= 0.97  # Réduire légèrement
            print("[UFA Analyzer] Performance faible détectée, ajustement -3%")
        elif avg_loss < 1.5:  # Bonne performance
            self.priors["avg_goals"] *= 1.03  # Augmenter légèrement
            print("[UFA Analyzer] Bonne performance détectée, ajustement +3%")
        
        # Ajuster draw_prior si beaucoup de nuls manqués
        for league, loss in league_losses.items():
            if loss > 3.0:
                self.priors["draw_prior"] = min(0.35, self.priors["draw_prior"] * 1.05)
                print(f"[UFA Analyzer] Ajustement draw_prior pour {league}")
        
        return self.priors
    
    def save_state(self, additional_data=None):
        """
        Sauvegarde l'état actuel de l'analyseur.
        
        Args:
            additional_data: Données supplémentaires à sauvegarder
        """
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "timestamp": json.dumps(None),  # Sera ajouté par trainer
            "priors": self.priors
        }
        
        if additional_data:
            state.update(additional_data)
        
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        print(f"[UFA Analyzer] État sauvegardé dans {STATE_PATH}")
