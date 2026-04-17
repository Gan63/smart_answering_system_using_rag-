import os
import jwt  # PyJWT
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from database.db_config import get_conn

SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")
if SECRET_KEY == "dev-only-insecure-secret-change-me":
    import warnings
    warnings.warn(
        "⚠️  JWT_SECRET env var is not set! Using insecure default. "
        "Set JWT_SECRET in Render → Your Service → Environment.",
        stacklevel=2,
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 # 8 hours

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class User(BaseModel):
    id: Optional[int] = None
    full_name: str
    email: str
    disabled: Optional[bool] = False

class UserInDB(User):
    password_hash: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_conn()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        return user
    except Exception as e:
        print(f"❌ Error fetching user: {e}")
        return None
    finally:
        conn.close()

def get_user_by_google_id(google_id: str) -> Optional[dict]:
    conn = get_conn()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
        user = cursor.fetchone()
        cursor.close()
        return user
    except Exception as e:
        print(f"❌ Error fetching user by Google ID: {e}")
        return None
    finally:
        conn.close()

def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return False
    if not verify_password(password, user["password_hash"]):
        return False
    return user

def register_user(full_name: str, email: str, password: str):
    conn = get_conn()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed. Please check if MySQL is running and credentials are correct."
        )
    
    try:
        cursor = conn.cursor()
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=400, detail="Email already registered")
        
        password_hash = get_password_hash(password)
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)",
            (full_name, email, password_hash)
        )
        conn.commit()
        cursor.close()
        return {"full_name": full_name, "email": email}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Registration failed due to database error: {str(e)}"
        )
def register_google_user(full_name: str, email: str, google_id: str, pfp_url: str = None):
    conn = get_conn()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (full_name, email, google_id, pfp_url) VALUES (%s, %s, %s, %s)",
            (full_name, email, google_id, pfp_url)
        )
        conn.commit()
        cursor.close()
        return {"full_name": full_name, "email": email, "google_id": google_id, "pfp_url": pfp_url}
    except Exception as e:
        print(f"❌ Error registering Google user: {e}")
        return None
    finally:
        conn.close()

def update_last_login(email: str):
    conn = get_conn()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_login = %s WHERE email = %s",
            (datetime.now(), email)
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"❌ Error updating last login: {e}")
    finally:
        conn.close()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except Exception:
        raise credentials_exception
    
    user = get_user_by_email(token_data.email)
    if user is None:
        raise credentials_exception
    
    return User(id=user['id'], full_name=user['full_name'], email=user['email'])

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    # All users are active for now
    return current_user
