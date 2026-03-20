import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from supabase import create_client, Client

from app.config import SUPABASE_URL, SUPABASE_KEY

# Supabase 클라이언트 초기화
# 개발 편의를 위해 환경변수가 비어있을 땐 None 허용
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def init_db():
    """
    Supabase 환경에서는 로컬 init_db가 불필요합니다.
    supabase_schema.sql 을 Supabase 대시보드에서 직접 실행해야 합니다.
    """
    pass


# ------------------------------------------------------------------
# Products
# ------------------------------------------------------------------

def seed_products_from_json(seed_path: str):
    """products_seed.json 에서 초기 상품 로드 (API 동기화 전 폴백)."""
    if not supabase: return
    with open(seed_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    
    upsert_data = []
    for it in items:
        upsert_data.append({
            "goods_code": it["goods_code"],
            "name": it["name"],
            "price": int(it["price"]),
            "image_url": it.get("image_url")
        })
    if upsert_data:
        supabase.table("products").upsert(upsert_data).execute()


def sync_products_from_api(products_from_api: list):
    """기프티쇼 API 0101에서 받은 상품 목록을 DB에 동기화."""
    if not supabase: return
    now = datetime.utcnow().isoformat()
    
    upsert_data = []
    for p in products_from_api:
        goods_state = p.get("goodsStateCd", "SALE")
        upsert_data.append({
            "goods_code": p.get("goodsCode"),
            "name": p.get("goodsName"),
            "price": int(p.get("salePrice") or 0),
            "discount_price": int(p.get("discountPrice") or 0),
            "image_url": p.get("goodsImgS"),
            "image_url_big": p.get("goodsImgB"),
            "brand_code": p.get("brandCode"),
            "brand_name": p.get("brandName"),
            "category": p.get("goodsTypeDtlNm"),
            "goods_state_cd": goods_state,
            "affiliate": p.get("affiliate"),
            "limit_day": int(p.get("limitDay") or 30),
            "mms_goods_img": p.get("mmsGoodsImg"),
            "updated_at": now
        })
    
    # Supabase upsert limitation (too many rows at once might fail), batch if necessary
    # Assuming list is < 1000 items usually
    if upsert_data:
        try:
            supabase.table("products").upsert(upsert_data).execute()
        except Exception as e:
            # 배치 분할 삽입 (Chunking)
            chunk_size = 200
            for i in range(0, len(upsert_data), chunk_size):
                supabase.table("products").upsert(upsert_data[i:i+chunk_size]).execute()


def list_products(only_sale: bool = True) -> List[Dict[str, Any]]:
    if not supabase: return []
    query = supabase.table("products").select("*")
    if only_sale:
        query = query.eq("goods_state_cd", "SALE")
    
    # 이름순 정렬
    resp = query.order("name", desc=False).execute()
    return resp.data


def get_product(goods_code: str):
    if not supabase: return None
    resp = supabase.table("products").select("*").eq("goods_code", goods_code).execute()
    return resp.data[0] if resp.data else None


# ------------------------------------------------------------------
# Users
# ------------------------------------------------------------------

def upsert_user(telegram_id: int, username: Optional[str], phone: Optional[str] = None):
    if not supabase: return
    now = datetime.utcnow().isoformat()
    
    # 기존 유저 조회하여 phone 유지 처리
    row = get_user(telegram_id)
    new_phone = phone
    if row and phone is None:
        new_phone = row.get("phone")
        
    data = {
        "telegram_id": telegram_id,
        "username": username,
        "phone": new_phone,
        "last_seen": now
    }
    supabase.table("users").upsert(data).execute()


def set_user_phone(telegram_id: int, phone: str):
    """현재 사용되지 않음 (전화번호 수집 안함)"""
    if not supabase: return
    now = datetime.utcnow().isoformat()
    supabase.table("users").update({"phone": phone, "last_seen": now}).eq("telegram_id", telegram_id).execute()


def get_user(telegram_id: int):
    if not supabase: return None
    resp = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return resp.data[0] if resp.data else None


def get_user_by_username(username: str):
    if not supabase: return None
    # Supabase ilike (대소문자 무시 검색)
    resp = supabase.table("users").select("*").ilike("username", username).execute()
    return resp.data[0] if resp.data else None


# ------------------------------------------------------------------
# Cart
# ------------------------------------------------------------------

def cart_get_items(telegram_id: int):
    if not supabase: return []
    # Foreign key 조인 (products)
    resp = supabase.table("cart_items").select("goods_code, qty, products!inner(name, price)").eq("telegram_id", telegram_id).execute()
    
    results = []
    for row in resp.data:
        p = row.get("products")
        if p:
            results.append({
                "goods_code": row["goods_code"],
                "qty": row["qty"],
                "name": p.get("name"),
                "price": p.get("price")
            })
    # 파이썬에서 정렬 (이름순)
    results.sort(key=lambda x: x["name"] if x["name"] else "")
    return results


def cart_set_qty(telegram_id: int, goods_code: str, qty: int):
    if not supabase: return
    if qty <= 0:
        supabase.table("cart_items").delete().eq("telegram_id", telegram_id).eq("goods_code", goods_code).execute()
    else:
        supabase.table("cart_items").upsert({
            "telegram_id": telegram_id,
            "goods_code": goods_code,
            "qty": qty
        }).execute()


def cart_clear(telegram_id: int):
    if not supabase: return
    supabase.table("cart_items").delete().eq("telegram_id", telegram_id).execute()


# ------------------------------------------------------------------
# Orders
# ------------------------------------------------------------------

def create_order(order_id: str, admin_telegram_id: int, total_price: int, status: str, created_at: str, payment_deadline_at: str):
    if not supabase: return
    supabase.table("orders").insert({
        "order_id": order_id,
        "admin_telegram_id": admin_telegram_id,
        "total_price": total_price,
        "status": status,
        "created_at": created_at,
        "payment_deadline_at": payment_deadline_at,
        "note": ""
    }).execute()


def add_order_item(order_id: str, goods_code: str, name: str, price: int, qty: int):
    if not supabase: return
    supabase.table("order_items").insert({
        "order_id": order_id,
        "goods_code": goods_code,
        "name": name,
        "price": price,
        "qty": qty
    }).execute()


def add_order_winner(order_id: str, winner_username: str, winner_telegram_id: Optional[int], winner_phone: Optional[str], send_status: str = "READY"):
    if not supabase: return
    supabase.table("order_winners").insert({
        "order_id": order_id,
        "winner_username": winner_username,
        "winner_telegram_id": winner_telegram_id,
        "winner_phone": winner_phone,
        "send_status": send_status
    }).execute()


def get_order(order_id: str):
    if not supabase: return None
    resp = supabase.table("orders").select("*").eq("order_id", order_id).execute()
    return resp.data[0] if resp.data else None


def set_order_status(order_id: str, status: str):
    if not supabase: return
    supabase.table("orders").update({"status": status}).eq("order_id", order_id).execute()


def list_orders_for_admin(admin_telegram_id: int, limit: int = 10):
    if not supabase: return []
    resp = supabase.table("orders").select("*").eq("admin_telegram_id", admin_telegram_id).order("created_at", desc=True).limit(limit).execute()
    return resp.data


def list_order_winners(order_id: str):
    if not supabase: return []
    resp = supabase.table("order_winners").select("*").eq("order_id", order_id).execute()
    return resp.data


def update_winner_send_result(order_id: str, winner_telegram_id: int, **fields):
    if not supabase: return
    # fields: send_status, tr_id, response_code, response_message, coupon_pin, coupon_img_url, order_no
    supabase.table("order_winners").update(fields).eq("order_id", order_id).eq("winner_telegram_id", winner_telegram_id).execute()


# ------------------------------------------------------------------
# Phase 3: Events (B2B Agency)
# ------------------------------------------------------------------

def create_event(event_id: str, admin_id: int, title: str, goods_code: str, winner_count: int, draw_type: str = "RANDOM"):
    if not supabase: return
    supabase.table("events").insert({
        "event_id": event_id,
        "admin_id": admin_id,
        "title": title,
        "goods_code": goods_code,
        "winner_count": winner_count,
        "draw_type": draw_type,
        "status": "OPEN"
    }).execute()

def get_event(event_id: str):
    if not supabase: return None
    resp = supabase.table("events").select("*").eq("event_id", event_id).execute()
    return resp.data[0] if resp.data else None

def set_event_status(event_id: str, status: str):
    if not supabase: return
    supabase.table("events").update({"status": status}).eq("event_id", event_id).execute()

def list_open_events():
    if not supabase: return []
    resp = supabase.table("events").select("*").eq("status", "OPEN").execute()
    return resp.data

def join_event(event_id: str, telegram_id: int, username: str, quiz_answer: Optional[str] = None):
    """참여자는 1회만 참여 가능 (UNIQUE 제약조건)"""
    if not supabase: return "NO_DB"
    try:
        supabase.table("event_participants").insert({
            "event_id": event_id,
            "telegram_id": telegram_id,
            "username": username,
            "quiz_answer": quiz_answer
        }).execute()
        return "SUCCESS"
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower() or getattr(e, "code", "") == "23505":
            return "ALREADY_JOINED"
        print("join_event error:", e)
        return "ERROR"

def get_event_participants(event_id: str):
    if not supabase: return []
    resp = supabase.table("event_participants").select("*").eq("event_id", event_id).order("joined_at", desc=False).execute()
    return resp.data

def update_participant_send_result(event_id: str, telegram_id: int, **fields):
    """
    fields: is_winner, send_status, tr_id, coupon_pin, coupon_img_url
    """
    if not supabase: return
    supabase.table("event_participants").update(fields).eq("event_id", event_id).eq("telegram_id", telegram_id).execute()
