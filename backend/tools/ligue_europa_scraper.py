#!/usr/bin/env python3
# /app/backend/tools/ligue_europa_scraper.py
"""
Scrapers spécifiques pour Ligue 2 et Europa League
Sources officielles :
- Ligue 2 : ligue1.com
- Europa League : uefa.com
"""

import requests
from bs4 import BeautifulSoup
import logging
import time
import random

logger = logging.getLogger(__name__)

# User agents pour éviter le blocage
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

# =========================================
# Scraper Ligue 2 (ligue1.com)
# =========================================

def scrape_ligue2():
    """
    Scrape le classement de Ligue 2 depuis ligue1.com
    
    Returns:
        list: Liste des équipes avec position, nom et points
    """
    url = "https://www.ligue1.com/classement/ligue2"
    
    try:
        logger.info(f"🌐 Scraping Ligue 2 depuis {url}")
        time.sleep(random.uniform(1.0, 2.0))  # Anti-ban
        
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code != 200:
            logger.error(f"❌ Ligue 2 HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        standings = []

        # Méthode 1 : table.standings-table
        rows = soup.select("table.standings-table tbody tr")
        
        if not rows:
            # Méthode 2 : Essayer d'autres sélecteurs
            rows = soup.select("table tbody tr")
        
        if not rows:
            # Méthode 3 : Chercher toutes les tables
            tables = soup.find_all("table")
            for table in tables:
                rows = table.select("tbody tr")
                if rows and len(rows) > 10:  # Au moins 10 équipes
                    break
        
        if not rows:
            logger.warning(f"⚠️ Aucune ligne trouvée pour Ligue 2")
            return None

        for row in rows:
            try:
                # Essayer plusieurs sélecteurs
                pos_elem = row.select_one(".position") or row.select_one("td:nth-child(1)")
                team_elem = row.select_one(".club-name") or row.select_one(".team-name") or row.select_one("td:nth-child(2)")
                pts_elem = row.select_one(".points") or row.select_one("td:nth-last-child(1)")
                
                if not (pos_elem and team_elem and pts_elem):
                    continue
                
                pos = pos_elem.get_text(strip=True)
                team = team_elem.get_text(strip=True)
                pts = pts_elem.get_text(strip=True)
                
                # Nettoyer et convertir
                try:
                    position = int(pos.replace('.', '').replace('#', '').strip())
                    points = int(pts.strip())
                except:
                    continue
                
                standings.append({
                    "team": team,
                    "position": position,
                    "points": points,
                    "played": None  # Pas toujours disponible
                })
            except Exception as e:
                logger.debug(f"Erreur parsing ligne Ligue 2: {e}")
                continue

        if standings:
            logger.info(f"✅ Ligue 2 : {len(standings)} équipes scrapées")
            return standings
        else:
            logger.warning(f"⚠️ Aucune donnée extraite pour Ligue 2")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erreur scraping Ligue 2: {e}")
        return None

# =========================================
# Scraper Europa League (uefa.com)
# =========================================

def scrape_europa_league():
    """
    Scrape le classement de l'Europa League depuis uefa.com
    
    Returns:
        list: Liste des équipes avec position, nom et points (tous groupes combinés)
    """
    url = "https://fr.uefa.com/uefaeuropaleague/standings/"
    
    try:
        logger.info(f"🌐 Scraping Europa League depuis {url}")
        time.sleep(random.uniform(1.5, 2.5))  # Anti-ban plus conservateur
        
        response = requests.get(url, headers=get_headers(), timeout=15)
        
        if response.status_code != 200:
            logger.error(f"❌ Europa League HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        all_standings = []
        position_counter = 1

        # Chercher les groupes
        groups = soup.select("section.standings-group") or soup.select("div.standings-group")
        
        if not groups:
            # Fallback : chercher toutes les tables
            groups = soup.find_all("table")
        
        if not groups:
            logger.warning(f"⚠️ Aucun groupe trouvé pour Europa League")
            return None

        for group in groups:
            try:
                # Nom du groupe (optionnel)
                group_name_elem = group.select_one("h3") or group.select_one("h2") or group.select_one(".group-name")
                group_name = group_name_elem.get_text(strip=True) if group_name_elem else "Unknown"
                
                # Lignes du tableau
                rows = group.select("table.standings-table tbody tr") or group.select("tbody tr")
                
                if not rows:
                    continue

                for row in rows:
                    try:
                        # Essayer plusieurs sélecteurs
                        team_elem = (row.select_one(".team-name") or 
                                   row.select_one(".club-name") or 
                                   row.select_one("td:nth-child(2)") or
                                   row.select_one("td.team"))
                        
                        pts_elem = (row.select_one(".points") or 
                                  row.select_one("td:nth-last-child(1)") or
                                  row.select_one("td.pts"))
                        
                        if not (team_elem and pts_elem):
                            continue
                        
                        team = team_elem.get_text(strip=True)
                        pts = pts_elem.get_text(strip=True)
                        
                        # Convertir
                        try:
                            points = int(pts.strip())
                        except:
                            continue
                        
                        all_standings.append({
                            "team": team,
                            "position": position_counter,
                            "points": points,
                            "played": None,
                            "group": group_name
                        })
                        
                        position_counter += 1
                        
                    except Exception as e:
                        logger.debug(f"Erreur parsing ligne Europa League: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Erreur parsing groupe Europa League: {e}")
                continue

        if all_standings:
            logger.info(f"✅ Europa League : {len(all_standings)} équipes scrapées")
            return all_standings
        else:
            logger.warning(f"⚠️ Aucune donnée extraite pour Europa League")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erreur scraping Europa League: {e}")
        return None

# =========================================
# Tests
# =========================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("🧪 Test 1: Ligue 2\n")
    ligue2 = scrape_ligue2()
    if ligue2:
        print(f"✅ {len(ligue2)} équipes")
        print("Top 5:")
        for team in ligue2[:5]:
            print(f"  {team['position']}. {team['team']} - {team['points']} pts")
    else:
        print("❌ Échec")
    
    print("\n" + "="*60 + "\n")
    
    print("🧪 Test 2: Europa League\n")
    europa = scrape_europa_league()
    if europa:
        print(f"✅ {len(europa)} équipes")
        print("Top 5:")
        for team in europa[:5]:
            print(f"  {team['position']}. {team['team']} - {team['points']} pts (Groupe: {team.get('group', 'N/A')})")
    else:
        print("❌ Échec")
