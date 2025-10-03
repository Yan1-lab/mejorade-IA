# utils/auth.py
import secrets
import bcrypt
from datetime import datetime
from utils.db import get_db, User

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def create_user(username: str, password: str, email: str = None):
    db = get_db()
    try:
        # check duplicates
        if db.query(User).filter((User.username == username) | (User.email == email)).first():
            return None, "Usuario o email ya existen"
        pwd_hash = hash_password(password)
        token = secrets.token_hex(32)
        user = User(username=username, email=email, password_hash=pwd_hash, token=token, last_login=datetime.utcnow())
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, None
    finally:
        db.close()

def authenticate_user(username_or_email: str, password: str):
    db = get_db()
    try:
        user = db.query(User).filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        if not user:
            return None, "Usuario no encontrado"
        if not verify_password(password, user.password_hash):
            return None, "Contraseña incorrecta"
        # ensure token exists
        if not user.token:
            user.token = secrets.token_hex(32)
        user.last_login = datetime.utcnow()
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, None
    finally:
        db.close()

def get_user_by_token(token: str):
    if not token:
        return None
    db = get_db()
    try:
        return db.query(User).filter(User.token == token).first()
    finally:
        db.close()

def rotate_user_token(user_id:int):
    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        user.token = secrets.token_hex(32)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.token
    finally:
        db.close()
