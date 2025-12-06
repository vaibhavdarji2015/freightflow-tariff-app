import os
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database configuration
# Use PostgreSQL in production (Railway/Render), SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL")

# Railway/Render provide DATABASE_URL starting with postgres://
# SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fallback to SQLite for local development
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./tariff_data.db"

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL settings
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

Base = declarative_base()

class Country(Base):
    __tablename__ = 'countries'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False)  # Removed unique constraint to allow duplicates
    export_zone = Column(Integer)
    import_zone = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Price(Base):
    __tablename__ = 'prices'
    
    id = Column(Integer, primary_key=True)
    service = Column(String, nullable=False)  # expedited, express, express_saver, express_plus
    item_type = Column(String, nullable=False)  # documents, non_documents, envelopes
    weight = Column(String, nullable=False)
    pricing_type = Column(String, default='fixed')  # fixed or per_kg
    zones = Column(JSON, nullable=False)  # {"zone_1": 4169, "zone_2": 4360, ...}
    created_at = Column(DateTime, default=datetime.utcnow)

class TariffCache(Base):
    __tablename__ = 'tariff_cache'
    
    id = Column(Integer, primary_key=True)
    pdf_url = Column(String, nullable=False)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    data = Column(JSON, nullable=False)

# Database setup
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
