from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import asyncpg
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from database import get_db_connection

# Load environment variables
load_dotenv()

# Security setup
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Pydantic models
class FounderRegister(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    company_name: str = None
    industry: str = None

class FounderLogin(BaseModel):
    email: EmailStr
    password: str

class FounderResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    company_name: str = None
    industry: str = None
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

# Database initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    conn = await get_db_connection()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS founders (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            company_name VARCHAR(255),
            industry VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_founders_email ON founders(email)
    """)
    await conn.close()
    print("Database initialized successfully!")
    
    # Setup validation module after app is created
    from startup_validation import setup_validation_module
    await setup_validation_module()
    
    yield

# FastAPI app
app = FastAPI(
    title="CoFoundr.AI Backend",
    description="Backend API for CoFoundr.AI - Connecting Startup Founders with AI-Powered Validation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include validation router after app is created
from startup_validation import router as validation_router
app.include_router(validation_router)

# Import get_current_user function from auth.py
from auth import get_current_user

# Utility functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

# Routes
@app.get("/")
async def root():
    return {"message": "CoFoundr.AI Backend API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    try:
        conn = await get_db_connection()
        await conn.fetchval("SELECT 1")
        await conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@app.post("/auth/register", response_model=dict)
async def register_founder(founder: FounderRegister):
    conn = await get_db_connection()
    
    try:
        # Check if email already exists
        existing_founder = await conn.fetchrow(
            "SELECT id FROM founders WHERE email = $1", founder.email
        )
        if existing_founder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password and create founder
        hashed_password = hash_password(founder.password)
        
        founder_id = await conn.fetchval("""
            INSERT INTO founders (email, password_hash, first_name, last_name, company_name, industry)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, founder.email, hashed_password, founder.first_name, founder.last_name, 
            founder.company_name, founder.industry)
        
        # Create access token
        access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": founder.email}, expires_delta=access_token_expires
        )
        
        return {
            "message": "Founder registered successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "founder_id": founder_id
        }
    finally:
        await conn.close()

@app.post("/auth/login", response_model=Token)
async def login_founder(founder: FounderLogin):
    conn = await get_db_connection()
    
    try:
        # Get founder from database
        db_founder = await conn.fetchrow(
            "SELECT * FROM founders WHERE email = $1 AND is_active = TRUE", founder.email
        )
        
        if not db_founder or not verify_password(founder.password, db_founder['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": founder.email}, expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        await conn.close()

@app.get("/auth/me", response_model=FounderResponse)
async def get_current_founder(current_founder = Depends(get_current_user)):
    return FounderResponse(
        id=current_founder['id'],
        email=current_founder['email'],
        first_name=current_founder['first_name'],
        last_name=current_founder['last_name'],
        company_name=current_founder['company_name'],
        industry=current_founder['industry'],
        is_active=current_founder['is_active'],
        created_at=current_founder['created_at']
    )

@app.post("/auth/logout")
async def logout_founder():
    return {"message": "Logged out successfully. Please remove the token from client storage."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)