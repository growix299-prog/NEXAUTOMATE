import os
import logging
from typing import Dict, Any, Optional, List
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
    logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE is not set in environment variables.")

# Initialize Supabase client using Service Role to bypass RLS policies
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE) if SUPABASE_URL and SUPABASE_SERVICE_ROLE else None

def get_db():
    return supabase

def get_product(product_id: str) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("products").select("*").eq("id", product_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
    return None

def create_user_if_not_exists(telegram_id: int, username: str, first_name: str) -> Dict[str, Any]:
    try:
        # Check if user exists
        response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        if response.data:
            return response.data[0]

        # Insert new user
        insert_response = supabase.table("users").insert({
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name
        }).execute()
        
        if insert_response.data:
            return insert_response.data[0]
    except Exception as e:
        logger.error(f"Error creating user {telegram_id}: {str(e)}")
    return {}

def create_order(telegram_id: int, product_id: str, payment_id: str, amount: float) -> Optional[Dict[str, Any]]:
    try:
        # Fetch internal user_id first
        user_response = supabase.table("users").select("id").eq("telegram_id", telegram_id).execute()
        user_id = user_response.data[0]["id"] if user_response.data else None

        insert_response = supabase.table("orders").insert({
            "user_id": user_id,
            "telegram_id": telegram_id,
            "product_id": product_id,
            "payment_id": payment_id,
            "amount": amount,
            "status": "PENDING",
            "delivery_status": "PENDING"
        }).execute()

        if insert_response.data:
            return insert_response.data[0]
    except Exception as e:
        logger.error(f"Error creating order for user {telegram_id}: {str(e)}")
    return None

def get_order_by_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    try:
        # Check by payment_id (which could be Razorpay Order ID or Payment ID)
        response = supabase.table("orders").select("*, products(*)").eq("payment_id", payment_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.error(f"Error fetching order by payment_id {payment_id}: {str(e)}")
    return None

def update_order_completed(order_id: str, delivery_status: str) -> bool:
    try:
        supabase.table("orders").update({
            "status": "COMPLETED",
            "delivery_status": delivery_status
        }).eq("id", order_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating order status for {order_id}: {str(e)}")
        return False

def get_unused_credential(product_id: str) -> Optional[Dict[str, Any]]:
    try:
        # Fetch one unused credential for the product
        response = supabase.table("credentials").select("*").eq("product_id", product_id).eq("status", "UNUSED").limit(1).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.error(f"Error fetching credential for product {product_id}: {str(e)}")
    return None

def mark_credential_used(credential_id: str) -> bool:
    try:
        supabase.table("credentials").update({
            "status": "USED"
        }).eq("id", credential_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error marking credential {credential_id} as USED: {str(e)}")
        return False

def create_ott_request(order_id: str, customer_email: str) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("ott_requests").insert({
            "order_id": order_id,
            "customer_email": customer_email,
            "status": "PENDING"
        }).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.error(f"Error creating OTT request for order {order_id}: {str(e)}")
    return None

def create_payment_record(razorpay_order_id: str, razorpay_payment_id: str, amount: float, verified: bool, payload: Dict[str, Any]) -> bool:
    try:
        supabase.table("payments").insert({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "amount": amount,
            "verified": verified,
            "payload": payload
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error logging payment record: {str(e)}")
        return False

def create_review(telegram_id: int, username: str, first_name: str, review_text: str) -> bool:
    try:
        supabase.table("reviews").insert({
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "review_text": review_text
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error creating review for {telegram_id}: {str(e)}")
        return False

