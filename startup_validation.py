from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import httpx
import asyncpg
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from database import get_db_connection
from auth import get_current_user
from dateutil import parser as date_parser

# Load environment variables
load_dotenv()

# Configuration - Updated API URL
OMNIDIM_API_KEY = os.getenv("OMNIDIM_API_KEY")
OMNIDIM_BASE_URL = "https://backend.omnidim.io/api/v1"
AGENT_ID = "2848"

# Security
security = HTTPBearer()

# Router
router = APIRouter(prefix="/validation", tags=["Startup Validation"])

# Pydantic Models for Validation Calls
class ValidationCallRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number to call in E.164 format (+1234567890)")

class ValidationCallResponse(BaseModel):
    call_id: str
    status: str
    message: str
    phone_number: str
    scheduled_at: datetime

class CallStatusResponse(BaseModel):
    call_id: str
    status: str
    duration: Optional[int] = None
    transcript: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class OmnidimCallReport(BaseModel):
    summary: Optional[str]
    sentiment: Optional[str]
    extracted_variables: Optional[Dict[str, Any]]
    full_conversation: Optional[str]
    interactions: Optional[List[Dict[str, Any]]]

# Webhook Models
class OmnidimWebhookPayload(BaseModel):
    call_id: int
    bot_id: int
    bot_name: str
    phone_number: str
    call_date: str
    user_email: str
    call_report: Optional[OmnidimCallReport]

# Database Models
class ValidationCall(BaseModel):
    id: int
    founder_id: int
    call_id: str
    phone_number: str
    startup_name: str
    industry: str
    business_model: str
    target_market: str
    additional_context: Optional[str]
    status: str
    duration: Optional[int]
    transcript: Optional[str]
    extracted_variables: Optional[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime]

# Database initialization function
async def init_validation_tables():
    """Initialize validation-related database tables"""
    conn = await get_db_connection()
    
    # Create validation_calls table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS validation_calls (
            id SERIAL PRIMARY KEY,
            founder_id INTEGER REFERENCES founders(id) ON DELETE CASCADE,
            call_id VARCHAR(255) UNIQUE NOT NULL,
            phone_number VARCHAR(20) NOT NULL,
            startup_name VARCHAR(255) NOT NULL,
            industry VARCHAR(100) NOT NULL,
            business_model TEXT NOT NULL,
            target_market TEXT NOT NULL,
            additional_context TEXT,
            status VARCHAR(50) DEFAULT 'initiated',
            duration INTEGER,
            transcript TEXT,
            extracted_variables JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_calls_founder_id ON validation_calls(founder_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_calls_call_id ON validation_calls(call_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_calls_status ON validation_calls(status)
    """)
    
    await conn.close()

# Utility functions
async def create_omnidim_call(phone_number: str, founder: dict) -> Dict[str, Any]:
    payload = {
        "agent_id": int(AGENT_ID),
        "to_number": phone_number,
        "call_context": {
            "customer_name": f"{founder['first_name']} {founder['last_name']}",
            "account_id": f"FOUNDR-{founder['id']}",
            "priority": "high"
        }
    }
    headers = {
        "Authorization": f"Bearer {OMNIDIM_API_KEY}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OMNIDIM_BASE_URL}/calls/dispatch",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to create call: {response.text}"
            )
        return response.json()

# API Endpoints

@router.post("/initiate-call", response_model=ValidationCallResponse)
async def initiate_validation_call(
    call_request: ValidationCallRequest,
    current_founder = Depends(get_current_user)
):
    """Initiate a startup validation call"""
    try:
        omnidim_response = await create_omnidim_call(call_request.phone_number, current_founder)
        # Omnidim returns 'requestId' as the unique identifier, not 'id'
        call_id = f"omnidim-{omnidim_response.get('requestId')}" if omnidim_response.get('requestId') else None
        if not call_id:
            raise HTTPException(
                status_code=500,
                detail=f"Omnidim did not return a requestId: {omnidim_response}"
            )
        conn = await get_db_connection()
        try:
            await conn.execute("""
                INSERT INTO validation_calls (
                    founder_id, call_id, phone_number, startup_name, industry, business_model, target_market, additional_context
                ) VALUES ($1, $2, $3, '', '', '', '', '')
            """,
                current_founder['id'],
                call_id,
                call_request.phone_number
            )
        finally:
            await conn.close()
        return ValidationCallResponse(
            call_id=call_id,
            status=omnidim_response.get('status', 'initiated'),
            message="Validation call initiated successfully",
            phone_number=call_request.phone_number,
            scheduled_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate validation call: {str(e)}"
        )

@router.get("/calls", response_model=List[CallStatusResponse])
async def get_validation_calls(
    status: Optional[str] = None,
    current_founder = Depends(get_current_user)
):
    """Get all validation calls for the current founder"""
    
    conn = await get_db_connection()
    try:
        query = """
            SELECT * FROM validation_calls 
            WHERE founder_id = $1
        """
        params = [current_founder['id']]
        
        if status:
            query += " AND status = $2"
            params.append(status)
            
        query += " ORDER BY created_at DESC"
        
        calls = await conn.fetch(query, *params)
        
        return [
            CallStatusResponse(
                call_id=call['call_id'],
                status=call['status'],
                duration=call['duration'],
                transcript=call['transcript'],
                analysis=call['extracted_variables'],
                created_at=call['created_at'],
                completed_at=call['completed_at']
            )
            for call in calls
        ]
        
    finally:
        await conn.close()

@router.get("/calls/{call_id}", response_model=CallStatusResponse)
async def get_validation_call(
    call_id: str,
    current_founder = Depends(get_current_user)
):
    """Get details of a specific validation call"""
    
    conn = await get_db_connection()
    try:
        call = await conn.fetchrow("""
            SELECT * FROM validation_calls 
            WHERE call_id = $1 AND founder_id = $2
        """, call_id, current_founder['id'])
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Validation call not found"
            )
        
        return CallStatusResponse(
            call_id=call['call_id'],
            status=call['status'],
            duration=call['duration'],
            transcript=call['transcript'],
            analysis=call['extracted_variables'],
            created_at=call['created_at'],
            completed_at=call['completed_at']
        )
        
    finally:
        await conn.close()

@router.post("/webhook")
async def omnidim_webhook(payload: OmnidimWebhookPayload):
    """Webhook endpoint for Omnidim call status updates"""
    conn = await get_db_connection()
    try:
        # Parse call_date robustly (handles both correct and incorrect formats)
        try:
            completed_at = date_parser.parse(payload.call_date)
        except Exception:
            completed_at = datetime.utcnow()

        await conn.execute("""
            UPDATE validation_calls 
            SET 
                status = 'completed',
                transcript = $1,
                extracted_variables = $2,
                completed_at = $3,
                updated_at = CURRENT_TIMESTAMP
            WHERE call_id = $4
        """,
            payload.call_report.full_conversation if payload.call_report else None,
            json.dumps(payload.call_report.extracted_variables) if payload.call_report and payload.call_report.extracted_variables else None,
            completed_at,
            f"omnidim-{payload.call_id}"
        )
        return {"status": "success", "message": "Webhook processed successfully"}
    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )
    finally:
        await conn.close()

@router.get("/call-status/{call_id}")
async def get_call_status_from_omnidim(
    call_id: str,
    current_founder = Depends(get_current_user)
):
    """Get real-time call status from Omnidim API"""
    
    headers = {
        "Authorization": f"Bearer {OMNIDIM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OMNIDIM_BASE_URL}/calls/{call_id}",
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Call not found"
                )
            elif response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to get call status: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to Omnidim API: {str(e)}"
        )

@router.delete("/calls/{call_id}")
async def cancel_validation_call(
    call_id: str,
    current_founder = Depends(get_current_user)
):
    """Cancel a validation call"""
    
    conn = await get_db_connection()
    try:
        # Check if call exists and belongs to the founder
        call = await conn.fetchrow("""
            SELECT * FROM validation_calls 
            WHERE call_id = $1 AND founder_id = $2
        """, call_id, current_founder['id'])
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Validation call not found"
            )
        
        if call['status'] in ['completed', 'failed']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a completed or failed call"
            )
        
        # Cancel call via Omnidim API
        headers = {
            "Authorization": f"Bearer {OMNIDIM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{OMNIDIM_BASE_URL}/calls/{call_id}",
                headers=headers,
                timeout=30.0
            )
        
        # Update status in database regardless of API response
        await conn.execute("""
            UPDATE validation_calls 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE call_id = $1
        """, call_id)
        
        return {"message": "Validation call cancelled successfully"}
        
    except httpx.RequestError as e:
        # Still update local status even if API call fails
        await conn.execute("""
            UPDATE validation_calls 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE call_id = $1
        """, call_id)
        
        return {"message": "Call cancelled locally, but API cancellation may have failed"}
        
    finally:
        await conn.close()

# Analytics endpoints
@router.get("/analytics/summary")
async def get_validation_analytics(
    current_founder = Depends(get_current_user)
):
    """Get validation analytics summary for the founder"""
    
    conn = await get_db_connection()
    try:
        # Get call statistics
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_calls,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_calls,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_calls,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as active_calls,
                AVG(duration) as avg_duration
            FROM validation_calls 
            WHERE founder_id = $1
        """, current_founder['id'])
        
        # Get recent calls with feedback scores
        recent_calls = await conn.fetch("""
            SELECT 
                startup_name, 
                status, 
                extracted_variables,
                created_at
            FROM validation_calls 
            WHERE founder_id = $1 
            ORDER BY created_at DESC 
            LIMIT 5
        """, current_founder['id'])
        
        # Calculate average feedback score
        feedback_scores = []
        for call in recent_calls:
            if call['extracted_variables'] and 'feedback_score' in call['extracted_variables']:
                try:
                    score = float(call['extracted_variables']['feedback_score'])
                    feedback_scores.append(score)
                except (ValueError, TypeError):
                    pass
        
        avg_feedback_score = sum(feedback_scores) / len(feedback_scores) if feedback_scores else None
        
        return {
            "total_calls": stats['total_calls'],
            "completed_calls": stats['completed_calls'],
            "failed_calls": stats['failed_calls'],
            "active_calls": stats['active_calls'],
            "average_duration": int(stats['avg_duration']) if stats['avg_duration'] else None,
            "average_feedback_score": round(avg_feedback_score, 2) if avg_feedback_score else None,
            "recent_validations": [
                {
                    "startup_name": call['startup_name'],
                    "status": call['status'],
                    "feedback_score": call['extracted_variables'].get('feedback_score') if call['extracted_variables'] else None,
                    "validated_at": call['created_at']
                }
                for call in recent_calls
            ]
        }
        
    finally:
        await conn.close()

# Initialize database tables when module is imported
import asyncio

async def setup_validation_module():
    """Setup validation module database tables"""
    await init_validation_tables()
    print("Validation module database tables initialized!")

# Export router and setup function
__all__ = ['router', 'setup_validation_module']