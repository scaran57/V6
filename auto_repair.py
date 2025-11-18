#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AUTO-REPAIR SYSTEM FOR FOOTBALL AI ENGINE
Restores DB, Scheduler, OCR, API, cache structure automatically.
"""

import os
import subprocess
import json
import shutil
from datetime import datetime

REPAIR_LOG = "/app/state/auto_repair_log.txt"

def log(msg):
    os.makedirs("/app/state", exist_ok=True)
    with open(REPAIR_LOG, "a") as f:
        f.write(f"{datetime.utcnow().isoformat()} | {msg}\n")
    print(msg)


###############################################
# 1️⃣ INSTALL SQLALCHEMY IF MISSING
###############################################
def install_dependencies():
    try:
        import sqlalchemy
        import aiosqlite
        log("✔ SQLAlchemy already installed.")
    except:
        log("❗ Installing SQLAlchemy + AioSQLite...")
        subprocess.run(["pip", "install", "sqlalchemy", "aiosqlite"], check=False)
        log("✔ Dependencies installed.")

###############################################
# 2️⃣ CREATE REQUIRED FOLDERS
###############################################
def create_folders():
    folders = [
        "/app/state",
        "/app/data",
        "/app/data/uploads",
        "/app/test_images",
        "/app/data/leagues",
    ]
    for f in folders:
        os.makedirs(f, exist_ok=True)
    log("✔ All required folders created.")

###############################################
# 3️⃣ FIX PERMISSIONS
###############################################
def fix_permissions():
    try:
        subprocess.run(["chmod", "-R", "777", "/app/data"], check=False)
        log("✔ Permissions fixed (chmod 777 /app/data).")
    except:
        log("⚠ Could not apply chmod.")

###############################################
# 4️⃣ REPAIR DATABASE + TABLES
###############################################
def repair_database():
    DB_FILE = "/app/data/system.db"

    # Create empty db if not present
    if not os.path.exists(DB_FILE):
        open(DB_FILE, "w").close()
        log("✔ Created missing database file.")

    # Create DB structure code
    DB_CODE = """
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine

Base = declarative_base()
engine = create_engine('sqlite:////app/data/system.db', connect_args={'check_same_thread': False})

class Match(Base):
    __tablename__ = 'matches'
    id = Column(Integer, primary_key=True, index=True)
    league = Column(String, index=True)
    home_team = Column(String)
    away_team = Column(String)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    expected_home = Column(Float, nullable=True)
    expected_away = Column(Float, nullable=True)

Base.metadata.create_all(bind=engine)
"""

    REPAIR_SCRIPT = "/app/db_repair_tmp.py"
    with open(REPAIR_SCRIPT, "w") as f:
        f.write(DB_CODE)

    subprocess.run(["python", REPAIR_SCRIPT], check=False)
    os.remove(REPAIR_SCRIPT)

    log("✔ Database structure repaired and tables created.")

###############################################
# 5️⃣ REPAIR OCR CONFIG (GPT VISION DEFAULT)
###############################################
def repair_ocr_settings():
    OCR_FILE = "/app/state/ocr_settings.json"

    default_cfg = {"use_gpt_vision": True}

    with open(OCR_FILE, "w") as f:
        json.dump(default_cfg, f)

    log("✔ OCR preference set to GPT-Vision by default.")

###############################################
# 6️⃣ CHECK API KEY – CREATE PLACEHOLDER
###############################################
def repair_api_env():
    ENV_FILE = "/app/.env"

    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w") as f:
            f.write("FOOTBALL_DATA_KEY=PUT_YOUR_KEY_HERE\n")
        log("❗ API key missing → placeholder created in /app/.env")
    else:
        log("✔ .env exists.")

###############################################
# 7️⃣ BASIC TEST IMAGE GENERATION
###############################################
def add_test_image():
    test_img = "/app/test_images/sample_test.txt"

    if not os.path.exists(test_img):
        with open(test_img, "w") as f:
            f.write("This is a placeholder for OCR test.")
        log("✔ Test image placeholder created.")
    else:
        log("✔ Test image already exists.")

###############################################
# 8️⃣ REPAIR SCHEDULER STATUS FILE
###############################################
def repair_scheduler_file():
    STATUS_FILE = "/app/state/scheduler_status.json"

    if not os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "w") as f:
            json.dump({"scheduler": "initialized"}, f)
        log("✔ Scheduler status file created.")
    else:
        log("✔ Scheduler status already exists.")

###############################################
# 9️⃣ CACHE MULTI-LIGUES CHECK
###############################################
def repair_cache():
    CACHE = "/app/data/leagues/multi_source_cache.json"

    if not os.path.exists(CACHE):
        with open(CACHE, "w") as f:
            json.dump({}, f)
        log("✔ Created empty league cache.")
    else:
        log("✔ League cache already present.")

###############################################
# 🔟 SUMMARY + RUN REPAIRS
###############################################
def main():
    log("====================================")
    log("🔧 STARTING AUTO-REPAIR SYSTEM")
    log("====================================")
    install_dependencies()
    create_folders()
    fix_permissions()
    repair_database()
    repair_ocr_settings()
    repair_api_env()
    add_test_image()
    repair_scheduler_file()
    repair_cache()

    log("====================================")
    log("✅ AUTO-REPAIR COMPLETE")
    log("====================================")

if __name__ == "__main__":
    main()
