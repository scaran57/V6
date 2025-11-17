"""
Modèles de base de données pour la persistance des images et analyses
Utilise SQLAlchemy avec SQLite
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON, Text, create_engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Base de données SQLite
DB_DIR = Path("/app/data/db")
DB_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_DIR}/emergent.db"

# Configuration pour SQLite avec support multi-thread
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class UploadedImage(Base):
    """Table des images uploadées par les utilisateurs"""
    __tablename__ = "uploaded_images"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    upload_time = Column(DateTime, default=datetime.utcnow, index=True)
    league = Column(String, nullable=True, index=True)
    home_team = Column(String, nullable=True)
    away_team = Column(String, nullable=True)
    bookmaker = Column(String, nullable=True)
    processed = Column(Boolean, default=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=True)
    
    # Relation inverse
    analysis_result = relationship("AnalysisResult", back_populates="images", foreign_keys=[analysis_id])

class AnalysisResult(Base):
    """Table des résultats d'analyse"""
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Scores extraits par OCR
    parsed_scores = Column(JSON, nullable=True)  # [{"home":1,"away":0,"cote":6.5}, ...]
    extracted_count = Column(Integer, default=0)
    
    # Résultat de prédiction
    most_probable_score = Column(String, nullable=True)  # "2-1"
    top3_scores = Column(JSON, nullable=True)  # [{"score":"2-1","prob":25.5}, ...]
    confidence = Column(Float, nullable=True)
    
    # Métadonnées OCR
    ocr_engine = Column(String, nullable=True)  # 'gpt-vision' or 'tesseract'
    ocr_confidence = Column(Float, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    
    # Paramètres utilisés pour le calcul
    diff_expected_used = Column(Float, nullable=True)
    base_expected_used = Column(Float, nullable=True)
    league_used = Column(String, nullable=True)
    
    # Score réel (pour apprentissage)
    real_score = Column(String, nullable=True)
    real_score_confirmed = Column(Boolean, default=False)
    real_score_source = Column(String, nullable=True)  # 'manual', 'api', 'scraper'
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    images = relationship("UploadedImage", back_populates="analysis_result", foreign_keys=[UploadedImage.analysis_id])

class LearningEvent(Base):
    """Table des événements d'apprentissage"""
    __tablename__ = "learning_events"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=True)
    
    league = Column(String, nullable=False, index=True)
    home_team = Column(String, nullable=True)
    away_team = Column(String, nullable=True)
    
    predicted_score = Column(String, nullable=False)
    real_score = Column(String, nullable=False)
    
    # Paramètres avant/après
    diff_expected_before = Column(Float, nullable=True)
    diff_expected_after = Column(Float, nullable=True)
    adjustment = Column(Float, nullable=True)
    
    # Métadonnées
    source = Column(String, nullable=True)  # 'manual', 'automatic'
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

def init_db():
    """Initialise la base de données et crée toutes les tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Base de données initialisée")
        
        # Vérifier les tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"📊 Tables créées: {', '.join(tables)}")
        
    except Exception as e:
        logger.error(f"❌ Erreur init DB: {e}")
        raise

def get_db():
    """Générateur de session pour FastAPI dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fonctions utilitaires
def get_recent_analyses(limit: int = 20):
    """Récupère les analyses récentes"""
    db = SessionLocal()
    try:
        analyses = db.query(AnalysisResult)\
            .order_by(AnalysisResult.created_at.desc())\
            .limit(limit)\
            .all()
        return analyses
    finally:
        db.close()

def get_unconfirmed_analyses(limit: int = 100):
    """Récupère les analyses sans score réel confirmé"""
    db = SessionLocal()
    try:
        analyses = db.query(AnalysisResult)\
            .filter(AnalysisResult.real_score_confirmed == False)\
            .filter(AnalysisResult.most_probable_score != None)\
            .order_by(AnalysisResult.created_at.desc())\
            .limit(limit)\
            .all()
        return analyses
    finally:
        db.close()

def confirm_real_score(analysis_id: int, real_score: str, source: str = "manual"):
    """Confirme le score réel d'une analyse"""
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisResult).get(analysis_id)
        if analysis:
            analysis.real_score = real_score
            analysis.real_score_confirmed = True
            analysis.real_score_source = source
            analysis.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"✅ Score réel confirmé pour analyse {analysis_id}: {real_score}")
            return True
        return False
    finally:
        db.close()

# Test du module
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*70)
    print("TEST MODULE MODELS")
    print("="*70)
    
    # Initialiser la DB
    init_db()
    
    # Test d'insertion
    db = SessionLocal()
    
    # Créer une image
    img = UploadedImage(
        filename="/app/data/uploads/test.jpg",
        original_filename="test.jpg",
        league="LaLiga",
        home_team="Real Madrid",
        away_team="Barcelona",
        bookmaker="Winamax"
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    print(f"\n✅ Image créée: ID={img.id}")
    
    # Créer une analyse
    analysis = AnalysisResult(
        parsed_scores=[{"home": 2, "away": 1, "cote": 8.5}],
        extracted_count=23,
        most_probable_score="2-1",
        top3_scores=[{"score": "2-1", "prob": 25.5}],
        confidence=0.755,
        ocr_engine="gpt-vision",
        diff_expected_used=2.1380,
        league_used="LaLiga"
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    print(f"✅ Analyse créée: ID={analysis.id}")
    
    # Lier l'image à l'analyse
    img.analysis_id = analysis.id
    img.processed = True
    db.commit()
    print(f"✅ Image liée à l'analyse")
    
    # Récupérer les analyses récentes
    recent = get_recent_analyses(5)
    print(f"\n📊 Analyses récentes: {len(recent)}")
    for a in recent:
        print(f"   - ID {a.id}: {a.most_probable_score} (confiance: {a.confidence})")
    
    db.close()
    print("\n✅ Tests terminés")
