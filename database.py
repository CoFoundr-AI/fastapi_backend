import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
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