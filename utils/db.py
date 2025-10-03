# utils/db.py
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    token = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=True)
    user_input = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="sessions")
    files = relationship("ChatFile", back_populates="session", cascade="all, delete-orphan")

class ChatFile(Base):
    __tablename__ = "chat_files"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    filename = Column(String(500))
    filepath = Column(String(1000))
    filetype = Column(String(50))
    extracted_text = Column(Text, nullable=True)
    session = relationship("ChatSession", back_populates="files")

# Module-level engine / SessionLocal (will be set via init_db)
engine = None
SessionLocal = None

def init_db(database_url: str):
    """Initialize engine and session factory. Call once from app with DATABASE_URL."""
    global engine, SessionLocal
    if not database_url:
        raise ValueError("database_url required")
    # For sqlite, need connect_args
    if database_url.startswith("sqlite"):
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

# Helper functions that use SessionLocal
def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db(database_url).")
    return SessionLocal()

def create_chat_session(user_id:int, title:str=None, user_input:str=None, assistant_response:str=None):
    db = get_db()
    try:
        s = ChatSession(user_id=user_id, title=title, user_input=user_input, assistant_response=assistant_response)
        db.add(s)
        db.commit()
        db.refresh(s)
        return s
    finally:
        db.close()

def get_sessions_by_user(user_id:int, limit=200):
    db = get_db()
    try:
        return db.query(ChatSession).filter(ChatSession.user_id==user_id).order_by(ChatSession.created_at.desc()).limit(limit).all()
    finally:
        db.close()

def get_session(user_id:int, session_id:int):
    db = get_db()
    try:
        return db.query(ChatSession).filter(ChatSession.user_id==user_id, ChatSession.id==session_id).first()
    finally:
        db.close()

def delete_session(session_id:int):
    db = get_db()
    try:
        s = db.query(ChatSession).filter(ChatSession.id==session_id).first()
        if not s:
            return False
        # delete files on disk if exist
        for f in s.files:
            try:
                if f.filepath and os.path.exists(f.filepath):
                    os.remove(f.filepath)
            except Exception:
                pass
        db.delete(s)
        db.commit()
        return True
    finally:
        db.close()

def delete_all_sessions_for_user(user_id:int):
    db = get_db()
    try:
        db.query(ChatSession).filter(ChatSession.user_id==user_id).delete()
        db.commit()
        return True
    finally:
        db.close()

def save_file_record(session_id:int, filename:str, filepath:str, filetype:str, extracted_text:str):
    db = get_db()
    try:
        f = ChatFile(session_id=session_id, filename=filename, filepath=filepath, filetype=filetype, extracted_text=extracted_text)
        db.add(f)
        db.commit()
        db.refresh(f)
        return f
    finally:
        db.close()

def get_files_for_session(session_id:int):
    db = get_db()
    try:
        return db.query(ChatFile).filter(ChatFile.session_id==session_id).all()
    finally:
        db.close()
