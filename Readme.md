# CoFoundr.AI Backend

FastAPI backend for CoFoundr.AI - A platform connecting startup founders.

## Features

- **User Authentication**: JWT-based authentication for startup founders
- **Registration & Login**: Simple email-based registration and login
- **PostgreSQL Database**: Cloud-hosted PostgreSQL database on Azure
- **Secure Password Handling**: Bcrypt password hashing
- **CORS Support**: Cross-origin resource sharing enabled
- **API Documentation**: Automatic OpenAPI/Swagger documentation

## Endpoints

### Authentication Endpoints

- `POST /auth/register` - Register a new founder
- `POST /auth/login` - Login and get JWT token
- `GET /auth/me` - Get current user profile (requires auth)
- `POST /auth/logout` - Logout (client-side token removal)

### Utility Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation

## Setup

1. **Install Dependencies**
   ```bash
   # Activate virtual environment
   source cofoundr_venv/bin/activate
   
   # Install packages
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   - Copy `.env.example` to `.env`
   - Update the JWT secret key in production
   - Database credentials are already configured for Azure PostgreSQL

3. **Run the Application**
   ```bash
   # Method 1: Direct Python
   python main.py
   
   # Method 2: Using uvicorn
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
   # Method 3: Using setup script
   chmod +x setup.sh
   ./setup.sh
   ```

4. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Redoc: http://localhost:8000/redoc

## Database Schema

### Founders Table
- `id` (SERIAL PRIMARY KEY)
- `email` (VARCHAR UNIQUE)
- `password_hash` (VARCHAR)
- `first_name` (VARCHAR)
- `last_name` (VARCHAR)
- `company_name` (VARCHAR, optional)
- `industry` (VARCHAR, optional)
- `is_active` (BOOLEAN, default: true)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

## API Usage Examples

### Register a new founder
```bash
curl -X POST "http://localhost:8000/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "founder@startup.com",
       "password": "securepassword123",
       "first_name": "John",
       "last_name": "Doe",
       "company_name": "TechStartup Inc",
       "industry": "Technology"
     }'
```

### Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "founder@startup.com",
       "password": "securepassword123"
     }'
```

### Get user profile (with token)
```bash
curl -X GET "http://localhost:8000/auth/me" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Security Features

- **Password Hashing**: Uses bcrypt for secure password storage
- **JWT Tokens**: Stateless authentication with configurable expiration
- **Input Validation**: Pydantic models for request validation
- **CORS Protection**: Configurable cross-origin resource sharing
- **Environment Variables**: Sensitive data stored in environment variables

## Database Connection

The application connects to Azure PostgreSQL Flexible Server with:
- SSL/TLS encryption
- Connection pooling for performance
- Automatic table creation on startup
- Error handling and logging

## Development

### Project Structure
```
fastapi_backend/
├── main.py              # FastAPI application
├── db.py                # Database models and operations
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not in git)
├── .env.example         # Environment template
├── setup.sh             # Setup script
└── README.md            # This file
```

### Adding New Features
1. Define Pydantic models for request/response
2. Add database operations in `db.py`
3. Create new endpoints in `main.py`
4. Update documentation

## Production Deployment

Before deploying to production:

1. **Security**
   - Change JWT secret key
   - Configure CORS origins properly
   - Enable HTTPS
   - Set DEBUG=False

2. **Database**
   - Review connection pool settings
   - Set up database backups
   - Configure monitoring

3. **Monitoring**
   - Set up logging
   - Add health checks
   - Monitor performance

## License

This project is part of CoFoundr.AI platform.