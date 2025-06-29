import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "require")

async def get_db_connection():
    """Create and return a database connection"""
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        ssl=DB_SSL_MODE
    )

async def init_database():
    """Initialize database tables"""
    conn = await get_db_connection()
    
    # Create founders table
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
    
    # Create index on email for faster lookups
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_founders_email ON founders(email)
    """)
    
    await conn.close()
    print("Database initialized successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_database())