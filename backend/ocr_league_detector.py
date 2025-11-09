#!/usr/bin/env python3
"""
Détecteur de Ligue Amélioré - Recherche dans le texte OCR
Détecte les marqueurs de ligues/compétitions dans le texte brut
"""

import re
from typing import Optional

# Patterns de détection de ligues (avec variantes)
LEAGUE_PATTERNS = {
    "Ligue1": [
        r"ligue\s*1",
        r"ligue\s*un",
        r"l1",
        r"ligue 1 mcdonald",
        r"championnat de france",
        r"french league"
    ],
    "LaLiga": [
        r"la\s*liga",
        r"laliga",
        r"liga\s*santander",
        r"liga\s*ea\s*sports",
        r"liga\s*espagnole",
        r"spanish\s*league",
        r"primera\s*division"
    ],
    "PremierLeague": [
        r"premier\s*league",
        r"epl",
        r"english\s*premier",
        r"barclays",
        r"league\s*anglaise"
    ],
    "Bundesliga": [
        r"bundesliga",
        r"buli",
        r"1\.\s*bundesliga",
        r"bundesliga\s*1",
        r"ligue\s*allemande",
        r"german\s*league"
    ],
    "SerieA": [
        r"serie\s*a",
        r"seria\s*a",
        r"calcio\s*serie\s*a",
        r"serie\s*a\s*tim",
        r"ligue\s*italienne",
        r"italian\s*league"
    ],
    "Ligue2": [
        r"ligue\s*2",
        r"ligue\s*deux",
        r"l2",
        r"championship\s*france"
    ],
    "PrimeiraLiga": [
        r"primeira\s*liga",
        r"liga\s*portugal",
        r"liga\s*nos",
        r"liga\s*betclic",
        r"portuguese\s*league",
        r"ligue\s*portugaise"
    ],
    "Eredivisie": [
        r"eredivisie",
        r"eredivise",
        r"dutch\s*league",
        r"ligue\s*neerlandaise"
    ],
    "Championship": [
        r"championship",
        r"efl\s*championship",
        r"english\s*championship"
    ],
    "ChampionsLeague": [
        r"champions\s*league",
        r"ucl",
        r"c1",
        r"uefa\s*champions",
        r"ligue\s*des\s*champions"
    ],
    "EuropaLeague": [
        r"europa\s*league",
        r"uel",
        r"c3",
        r"uefa\s*europa"
    ]
}

def detect_league_from_text(text: str) -> Optional[str]:
    """
    Détecte la ligue à partir du texte OCR brut.
    Retourne le nom de la ligue ou None si aucune détection.
    """
    if not text:
        return None
    
    # Normaliser le texte
    text_lower = text.lower()
    
    # Chercher chaque pattern
    for league_name, patterns in LEAGUE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return league_name
    
    return None

def detect_multiple_leagues_from_text(text: str) -> list:
    """
    Détecte toutes les ligues présentes dans le texte.
    Utile pour les images contenant plusieurs matchs de différentes ligues.
    Retourne une liste de tuples (league_name, position)
    """
    if not text:
        return []
    
    text_lower = text.lower()
    detected = []
    
    for league_name, patterns in LEAGUE_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                detected.append((league_name, match.start()))
    
    # Trier par position dans le texte
    detected.sort(key=lambda x: x[1])
    
    return detected

def extract_league_context(text: str, team1: str, team2: str) -> Optional[str]:
    """
    Essaie de déterminer la ligue en fonction du contexte autour des équipes.
    Cherche la ligue mentionnée le plus proche des noms d'équipes.
    """
    if not text or not team1:
        return None
    
    text_lower = text.lower()
    team1_lower = team1.lower()
    team2_lower = team2.lower() if team2 else ""
    
    # Trouver les positions des équipes
    team1_pos = text_lower.find(team1_lower)
    team2_pos = text_lower.find(team2_lower) if team2_lower else -1
    
    if team1_pos == -1:
        # Si on ne trouve pas team1, chercher globalement
        return detect_league_from_text(text)
    
    # Détecter toutes les ligues avec leur position
    leagues = detect_multiple_leagues_from_text(text)
    
    if not leagues:
        return None
    
    # Trouver la ligue la plus proche des équipes
    min_distance = float('inf')
    closest_league = None
    
    for league_name, league_pos in leagues:
        # Distance par rapport à team1
        dist1 = abs(league_pos - team1_pos)
        
        # Distance par rapport à team2 (si présent)
        if team2_pos != -1:
            dist2 = abs(league_pos - team2_pos)
            dist = min(dist1, dist2)
        else:
            dist = dist1
        
        if dist < min_distance:
            min_distance = dist
            closest_league = league_name
    
    return closest_league

# Pour tests
if __name__ == "__main__":
    # Test 1
    text1 = "Ligue 1 McDonald's - PSG vs Marseille"
    print(f"Text: {text1}")
    print(f"Detected: {detect_league_from_text(text1)}")
    print()
    
    # Test 2
    text2 = "LaLiga EA Sports - Real Madrid vs Barcelona"
    print(f"Text: {text2}")
    print(f"Detected: {detect_league_from_text(text2)}")
    print()
    
    # Test 3
    text3 = "Bundesliga - Bayern vs Dortmund"
    print(f"Text: {text3}")
    print(f"Detected: {detect_league_from_text(text3)}")
    print()
    
    # Test 4: Multiple leagues
    text4 = """
    Ligue 1: PSG vs Lyon
    LaLiga: Real vs Barca
    Premier League: Arsenal vs Man City
    """
    print(f"Text: Multiple leagues")
    print(f"Detected: {detect_multiple_leagues_from_text(text4)}")
