import os, re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

from app.config import (
    TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_IDS, SUPER_ADMIN_TELEGRAM_IDS,
    GIFTISHOW_API_BASE, GIFTISHOW_CUSTOM_AUTH_CODE, GIFTISHOW_CUSTOM_AUTH_TOKEN,
    GIFTISHOW_USER_ID, GIFTISHOW_CALLBACK_NO, GIFTISHOW_DEV_YN,
    BANK_INFO, PAYMENT_DEADLINE_MINUTES,
)
from app import db
from app.giftishow import GiftishowClient, GiftishowError

STATE_KEY = "state"

CB_MENU = "menu"
CB_QTY = "qty"
CB_QTYIN = "qtyin"
CB_CATALOG = "cat"
CB_CART = "cart"
CB_CLEAR = "clear"
CB_CHECKOUT = "checkout"
CB_PAID = "paid"
CB_APPROVE = "appr"
CB_REJECT = "rej"
CB_ORDER = "order"

CATALOG_PAGE_SIZE = 6


def _get_client() -> GiftishowClient:
    """기프티쇼 API 클라이언트 인스턴스 생성."""
    return GiftishowClient(
        base_url=GIFTISHOW_API_BASE,
        custom_auth_code=GIFTISHOW_CUSTOM_AUTH_CODE,
        custom_auth_token=GIFTISHOW_CUSTOM_AUTH_TOKEN,
        user_id=GIFTISHOW_USER_ID,
        dev_yn=GIFTISHOW_DEV_YN,
    )


def is_admin(uid: int) -> bool:
    return uid in ADMIN_TELEGRAM_IDS


def is_super(uid: int) -> bool:
    return uid in SUPER_ADMIN_TELEGRAM_IDS


def normalize_username(s: str):
    s = s.strip()
    if not s:
        return None
    if s.startswith("@"):
        s = s[1:]
    s = s.strip()
    if re.fullmatch(r"[A-Za-z0-9_]{3,32}", s):
        return s
    return None


def gen_order_id():
    return "ORD-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def gen_tr_id(order_id: str, idx: int):
    """규격서 권고: service_yyyyMMdd_seq (25자 이하)"""
    date_part = datetime.now().strftime("%Y%m%d")
    seq = f"{idx:04d}"
    return f"rktgft_{date_part}_{seq}"[:25]


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 상품목록", callback_data=f"{CB_MENU}:catalog")],
        [InlineKeyboardButton("🛒 장바구니", callback_data=f"{CB_MENU}:cart")],
        [InlineKeyboardButton("📑 주문내역", callback_data=f"{CB_MENU}:orders")],
    ])


def catalog_list_kb(products, page: int):
    total_pages = max(1, (len(products) + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * CATALOG_PAGE_SIZE
    end = min(len(products), start + CATALOG_PAGE_SIZE)
    kb = []
    for idx in range(start, end):
        p = products[idx]
        kb.append([InlineKeyboardButton(f"{idx+1}. {p['name']}", callback_data=f"{CB_CATALOG}:open:{idx}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ 이전", callback_data=f"{CB_CATALOG}:list:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("다음 ➡️", callback_data=f"{CB_CATALOG}:list:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")])
    return InlineKeyboardMarkup(kb)


def cart_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 주문 진행", callback_data=f"{CB_CHECKOUT}:start")],
        [InlineKeyboardButton("🧹 장바구니 비우기", callback_data=f"{CB_CLEAR}:cart")],
        [InlineKeyboardButton("⬅️ 메뉴", callback_data=f"{CB_MENU}:home")],
    ])


def product_kb(goods_code: str, qty: int, page: int):
    qty = max(1, min(999, int(qty)))
    list_page = page // CATALOG_PAGE_SIZE
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data=f"{CB_QTY}:{goods_code}:{qty-1}:{page}"),
            InlineKeyboardButton(str(qty), callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"{CB_QTY}:{goods_code}:{qty+1}:{page}"),
        ],
        [InlineKeyboardButton("✍️ 수량 입력", callback_data=f"{CB_QTYIN}:{goods_code}:{page}")],
        [InlineKeyboardButton("🛒 장바구니 담기", callback_data=f"{CB_CART}:add:{goods_code}:{qty}:{page}")],
        [InlineKeyboardButton("⬅️ 목록으로", callback_data=f"{CB_CATALOG}:list:{list_page}")],
        [InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")],
    ])


def format_cart(items):
    if not items:
        return "🛒 장바구니가 비어있습니다.", 0
    total = 0
    lines = ["🛒 <b>장바구니</b>", ""]
    for i, it in enumerate(items, 1):
        subtotal = it["price"] * it["qty"]
        total += subtotal
        lines.append(f"{i}. {it['name']} x {it['qty']} = <b>{subtotal:,}원</b>")
    lines.append("")
    lines.append("—")
    lines.append(f"총 금액: <b>{total:,}원</b>")
    return "\n".join(lines), total


def build_winner_preview(items, matched, unmatched):
    cart_text, _ = format_cart(items)
    lines = [cart_text, "", "🎯 <b>당첨자 확인</b>", f"✅ 매칭 성공: <b>{len(matched)}</b>명"]
    if matched:
        lines.extend([f"@{m['username']}" for m in matched[:20]])
        if len(matched) > 20:
            lines.append(f"...(+{len(matched)-20})")
    lines.append("")
    lines.append(f"❌ 매칭 실패(/start 필요): <b>{len(unmatched)}</b>명")
    if unmatched:
        lines.extend([f"@{u}" for u in unmatched[:20]])
        if len(unmatched) > 20:
            lines.append(f"...(+{len(unmatched)-20})")
    lines.append("")
    lines.append("위 내용으로 주문을 생성할까요?")
    return "\n".join(lines)


# ==================== Command Handlers ====================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username)
    if is_admin(u.id):
        await update.message.reply_text(
            "🛒 <b>기프티콘 주문센터</b>\n\n아래 메뉴를 선택하세요.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
    else:
        await update.message.reply_text(
            "안녕하세요! 당첨자 수령을 위해 /start만 해두시면 됩니다."
        )


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username)
    row = db.get_user(u.id)
    await update.message.reply_text(
        f"telegram_id: {u.id}\nusername: @{row['username'] if row and row['username'] else '(없음)'}"
    )


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 명령: /sync — 기프티쇼에서 상품 목록 동기화"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("관리자만 사용 가능합니다.")
        return

    if not GIFTISHOW_CUSTOM_AUTH_CODE:
        await update.message.reply_text("⚠️ 기프티쇼 API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    await update.message.reply_text("🔄 기프티쇼 상품 동기화 중...")

    try:
        client = _get_client()
        all_products = []
        page = 1
        while True:
            resp = client.list_products(start=page, size=100)
            result = resp.get("result") or {}
            goods_list = result.get("goodsList") or []
            if not goods_list:
                break
            all_products.extend(goods_list)
            page += 1
            # 안전장치: 최대 50 페이지
            if page > 50:
                break

        if all_products:
            db.sync_products_from_api(all_products)
            sale_count = sum(1 for p in all_products if p.get("goodsStateCd") == "SALE")
            await update.message.reply_text(
                f"✅ 상품 동기화 완료!\n"
                f"전체: <b>{len(all_products)}</b>개\n"
                f"판매중: <b>{sale_count}</b>개",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text("⚠️ 기프티쇼에서 상품을 가져오지 못했습니다.")
    except GiftishowError as e:
        await update.message.reply_text(f"❌ API 오류: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ 동기화 실패: {e}")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 명령: /balance — 비즈머니 잔액 조회"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("관리자만 사용 가능합니다.")
        return

    if not GIFTISHOW_CUSTOM_AUTH_CODE:
        await update.message.reply_text("⚠️ 기프티쇼 API 키가 설정되지 않았습니다.")
        return

    try:
        client = _get_client()
        resp = client.get_bizmoney_balance()
        balance = resp.get("balance", "0")
        await update.message.reply_text(
            f"💰 <b>비즈머니 잔액</b>\n{int(balance):,}원",
            parse_mode=ParseMode.HTML,
        )
    except GiftishowError as e:
        await update.message.reply_text(f"❌ API 오류: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ 조회 실패: {e}")


# ==================== Inline Menu Handlers ====================

async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":", 1)[1]
    if action == "home":
        await q.edit_message_text(
            "🛒 <b>기프티콘 주문센터</b>\n\n아래 메뉴를 선택하세요.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
        return
    if action == "catalog":
        await show_catalog_list(q, context, 0)
        return
    if action == "cart":
        await show_cart(q, context)
        return
    if action == "orders":
        await show_orders(q, context)
        return


async def show_catalog(q, context, page: int):
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    products = db.list_products()
    if not products:
        await q.edit_message_text("등록된 상품이 없습니다. /sync 명령으로 상품을 동기화하세요.")
        return
    page = max(0, min(page, len(products) - 1))
    p = products[page]
    qty_map = context.user_data.get("browse_qty_map") or {}
    qty = qty_map.get(p["goods_code"], 1)
    text = (
        f"📦 <b>상품 {page+1}/{len(products)}</b>\n\n"
        f"<b>{p['name']}</b>\n"
        f"가격: <b>{int(p['price']):,}원</b>\n"
        f"코드: <code>{p['goods_code']}</code>\n"
    )
    if p.get("brand_name"):
        text += f"브랜드: {p['brand_name']}\n"
    if p.get("image_url"):
        text += f"이미지: {p['image_url']}\n"
    context.user_data["product_view"] = {
        "chat_id": q.message.chat_id,
        "message_id": q.message.message_id,
        "goods_code": p["goods_code"],
        "page": int(page),
    }
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=product_kb(p["goods_code"], qty, page))


async def show_catalog_list(q, context, page: int):
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    products = db.list_products()
    if not products:
        await q.edit_message_text("등록된 상품이 없습니다. /sync 명령으로 상품을 동기화하세요.")
        return
    total_pages = max(1, (len(products) + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    text = f"📦 <b>상품목록</b> (페이지 {page+1}/{total_pages})\n\n원하는 상품을 선택하세요."
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=catalog_list_kb(products, page))


async def on_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) < 3:
        return
    kind = parts[1]
    arg = parts[2]
    if kind == "list":
        await show_catalog_list(q, context, int(arg))
        return
    if kind in ("open", "page"):
        await show_catalog(q, context, int(arg))
        return


async def on_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, goods_code, qty_s, page_s = q.data.split(":")
    qty = max(1, min(999, int(qty_s)))
    page = int(page_s)
    qty_map = context.user_data.get("browse_qty_map") or {}
    qty_map[goods_code] = qty
    context.user_data["browse_qty_map"] = qty_map
    context.user_data["product_view"] = {
        "chat_id": q.message.chat_id,
        "message_id": q.message.message_id,
        "goods_code": goods_code,
        "page": page,
    }
    try:
        await q.edit_message_reply_markup(reply_markup=product_kb(goods_code, qty, page))
    except BadRequest:
        await show_catalog(q, context, page)


async def on_qtyin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    parts = q.data.split(":")
    if len(parts) < 3:
        return
    goods_code = parts[1]
    page = int(parts[2])
    context.user_data["pending_qty_input"] = {
        "chat_id": q.message.chat_id,
        "message_id": q.message.message_id,
        "goods_code": goods_code,
        "page": page,
    }
    await context.bot.send_message(
        chat_id=q.from_user.id,
        text="✍️ 수량을 숫자로 입력해 주세요. (예: 25)\n취소하려면 '취소' 라고 보내세요.",
    )


async def on_qty_input_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return False
    uid = update.effective_user.id
    if not is_admin(uid):
        return False
    pending = context.user_data.get("pending_qty_input")
    if not pending:
        return False
    raw = (update.message.text or "").strip()
    if raw.lower() in ("취소", "cancel", "/cancel"):
        context.user_data.pop("pending_qty_input", None)
        await update.message.reply_text("✅ 수량 입력을 취소했습니다.")
        return True
    if not re.fullmatch(r"\d{1,4}", raw):
        await update.message.reply_text("숫자만 입력해 주세요. (예: 25)\n취소하려면 '취소' 라고 보내세요.")
        return True
    qty = int(raw)
    if qty < 1 or qty > 999:
        await update.message.reply_text("수량은 1~999 사이로 입력해 주세요.")
        return True
    goods_code = pending["goods_code"]
    page = int(pending["page"])
    qty_map = context.user_data.get("browse_qty_map") or {}
    qty_map[goods_code] = qty
    context.user_data["browse_qty_map"] = qty_map
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=pending["chat_id"],
            message_id=pending["message_id"],
            reply_markup=product_kb(goods_code, qty, page),
        )
    except Exception:
        pass
    context.user_data.pop("pending_qty_input", None)
    await update.message.reply_text(f"✅ 수량을 {qty}로 설정했습니다.")
    return True


async def on_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if parts[1] == "add":
        _, _, goods_code, qty_s, page_s = parts
        qty = int(qty_s)
        items = db.cart_get_items(q.from_user.id)
        cur = next((it for it in items if it["goods_code"] == goods_code), None)
        new_qty = qty + (cur["qty"] if cur else 0)
        db.cart_set_qty(q.from_user.id, goods_code, new_qty)
        list_page = int(page_s) // CATALOG_PAGE_SIZE
        await q.edit_message_text(
            "✅ 장바구니에 담았습니다.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 장바구니 보기", callback_data=f"{CB_MENU}:cart")],
                [InlineKeyboardButton("📦 계속 쇼핑", callback_data=f"{CB_CATALOG}:list:{list_page}")],
                [InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")],
            ]),
        )


async def show_cart(q, context):
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    items = db.cart_get_items(q.from_user.id)
    text, _ = format_cart(items)
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=cart_kb())


async def on_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    db.cart_clear(q.from_user.id)
    await q.edit_message_text("🧹 장바구니를 비웠습니다.", reply_markup=admin_menu())


# ==================== Checkout Flow ====================

async def on_checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    items = db.cart_get_items(q.from_user.id)
    if not items:
        await q.edit_message_text("장바구니가 비어있습니다.", reply_markup=admin_menu())
        return
    context.user_data[STATE_KEY] = {"mode": "await_winners"}
    cart_text, _ = format_cart(items)
    await q.edit_message_text(
        cart_text + "\n\n🎯 <b>당첨자 @닉네임</b>을 한 줄에 한 명씩 붙여넣어 주세요.\n예)\n@winner1\n@winner2",
        parse_mode=ParseMode.HTML,
    )


async def on_winners_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return False
    if not is_admin(update.effective_user.id):
        return False
    state = context.user_data.get(STATE_KEY) or {}
    raw = update.message.text or ""
    fallback = bool(raw and "@" in raw and db.cart_get_items(update.effective_user.id))
    if state.get("mode") != "await_winners" and not fallback:
        return False

    tokens = re.split(r"[\s,]+", raw.strip())
    usernames = []
    seen = set()
    for t in tokens:
        u = normalize_username(t)
        if not u:
            continue
        lu = u.lower()
        if lu in seen:
            continue
        seen.add(lu)
        usernames.append(u)
    if not usernames:
        await update.message.reply_text("유효한 @닉네임이 없습니다. 다시 보내주세요.")
        return True

    matched = []
    unmatched = []
    for u in usernames:
        row = db.get_user_by_username(u)
        if not row:
            unmatched.append(u)
            continue
        matched.append({"username": u, "telegram_id": row["telegram_id"]})

    state["mode"] = "preview_order"
    state["matched"] = matched
    state["unmatched"] = unmatched
    context.user_data[STATE_KEY] = state

    items = db.cart_get_items(update.effective_user.id)
    preview_text = build_winner_preview(items, matched, unmatched)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 주문 생성", callback_data=f"{CB_CHECKOUT}:create")],
        [InlineKeyboardButton("🔁 다시 입력", callback_data=f"{CB_CHECKOUT}:retry")],
        [InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")],
    ])
    await update.message.reply_text(preview_text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return True


async def on_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handled = await on_qty_input_text(update, context)
    if handled:
        return
    handled = await on_winners_text(update, context)
    if handled:
        return


async def on_checkout_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    action = q.data.split(":", 1)[1]
    if action == "retry":
        context.user_data[STATE_KEY] = {"mode": "await_winners"}
        await q.edit_message_text("🎯 당첨자 @닉네임을 다시 붙여넣어 주세요.")
        return
    if action == "create":
        state = context.user_data.get(STATE_KEY) or {}
        matched = state.get("matched") or []
        items = db.cart_get_items(q.from_user.id)
        if not items:
            await q.edit_message_text("장바구니가 비어있습니다.", reply_markup=admin_menu())
            return
        skus = list({it["goods_code"] for it in items})
        if len(skus) != 1:
            await q.edit_message_text("MVP는 장바구니 1개 상품만 지원합니다.", reply_markup=admin_menu())
            return
        goods_code = skus[0]
        qty = sum(it["qty"] for it in items)
        if len(matched) != qty:
            await q.edit_message_text(f"수량({qty})과 당첨자({len(matched)}) 수가 다릅니다.", reply_markup=admin_menu())
            return

        total = sum(it["price"] * it["qty"] for it in items)
        order_id = gen_order_id()
        created = datetime.now().isoformat()
        deadline = (datetime.now() + timedelta(minutes=PAYMENT_DEADLINE_MINUTES)).isoformat()

        db.create_order(order_id, q.from_user.id, total, "PENDING_PAYMENT", created, deadline)
        for it in items:
            db.add_order_item(order_id, it["goods_code"], it["name"], it["price"], it["qty"])
        for m in matched:
            db.add_order_winner(order_id, m["username"], m["telegram_id"], "01000000000", "READY")
        db.cart_clear(q.from_user.id)
        context.user_data[STATE_KEY] = {}

        text = (
            f"🧾 <b>주문 생성 완료</b>\n\n"
            f"주문번호: <code>{order_id}</code>\n"
            f"상품코드: <code>{goods_code}</code>\n"
            f"수량: <b>{qty}</b>\n"
            f"총 금액: <b>{total:,}원</b>\n\n"
            f"💳 <b>입금 안내</b>\n{BANK_INFO}\n"
            f"입금기한: {PAYMENT_DEADLINE_MINUTES}분\n\n"
            f"입금 후 아래 버튼을 눌러주세요."
        )
        await q.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ 입금완료 요청", callback_data=f"{CB_PAID}:{order_id}")],
                [InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")],
            ]),
        )


# ==================== Payment & Approval ====================

async def on_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except BadRequest:
        pass
    order_id = q.data.split(":", 1)[1]
    order = db.get_order(order_id)
    if not order:
        await q.edit_message_text("주문을 찾을 수 없습니다.", reply_markup=admin_menu())
        return
    if q.from_user.id != order["admin_telegram_id"]:
        await q.edit_message_text("이 주문의 관리자만 요청할 수 있습니다.")
        return
    db.set_order_status(order_id, "WAITING_APPROVAL")
    await q.edit_message_text("✅ 입금완료 요청이 접수되었습니다. 승인 후 발송됩니다.", reply_markup=admin_menu())

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("승인 ✅", callback_data=f"{CB_APPROVE}:{order_id}")],
        [InlineKeyboardButton("거절 ❌", callback_data=f"{CB_REJECT}:{order_id}")],
    ])
    for sid in SUPER_ADMIN_TELEGRAM_IDS:
        try:
            await context.bot.send_message(
                chat_id=sid,
                text=f"💰 <b>입금 확인 요청</b>\n주문번호: <code>{order_id}</code>\n관리자ID: {order['admin_telegram_id']}\n금액: <b>{order['total_price']:,}원</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        except Exception:
            pass


async def on_approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except BadRequest:
        pass
    uid = q.from_user.id
    if not is_super(uid):
        await q.edit_message_text("슈퍼관리자만 가능합니다.")
        return
    action, order_id = q.data.split(":", 1)
    order = db.get_order(order_id)
    if not order:
        await q.edit_message_text("주문을 찾을 수 없습니다.")
        return
    if order["status"] != "WAITING_APPROVAL":
        await q.edit_message_text(f"현재 주문 상태: {order['status']}")
        return
    if action == CB_REJECT:
        db.set_order_status(order_id, "REJECTED")
        await q.edit_message_text("거절했습니다.")
        try:
            await context.bot.send_message(chat_id=order["admin_telegram_id"], text=f"❌ 주문 {order_id} 입금확인이 거절되었습니다.")
        except Exception:
            pass
        return

    # === 승인 → 쿠폰 발송 ===
    db.set_order_status(order_id, "SENDING")
    await q.edit_message_text("승인했습니다. 발송 시작!")
    try:
        await context.bot.send_message(chat_id=order["admin_telegram_id"], text=f"✅ 주문 {order_id} 승인. 발송을 시작합니다.")
    except Exception:
        pass

    client = _get_client()
    winners = db.list_order_winners(order_id)

    # 상품코드 조회
    from app.db import conn as _conn
    with _conn() as c:
        row = c.execute("SELECT goods_code FROM order_items WHERE order_id=? LIMIT 1", (order_id,)).fetchone()
        goods_code = row["goods_code"] if row else None

    # 발송 전 비즈머니 잔액 확인 (선택적)
    try:
        balance_resp = client.get_bizmoney_balance()
        balance = int(balance_resp.get("balance", "0"))
        if balance < int(order["total_price"]):
            db.set_order_status(order_id, "FAILED")
            await context.bot.send_message(
                chat_id=order["admin_telegram_id"],
                text=f"❌ 비즈머니 잔액 부족\n잔액: {balance:,}원 / 필요: {int(order['total_price']):,}원",
            )
            return
    except Exception:
        pass  # 잔액 확인 실패해도 발송 시도

    success = 0
    fail = 0
    for idx, w in enumerate(winners, 1):
        tid = w["winner_telegram_id"]
        phone = "01000000000"  # 임의 전화번호 사용
        if not tid:
            fail += 1
            db.update_winner_send_result(order_id, tid, send_status="FAILED", response_code="NO_TID", response_message="텔레그램ID 미등록")
            continue

        tr_id = gen_tr_id(order_id, idx)
        try:
            resp = client.send_coupon(
                tr_id=tr_id,
                phone_no=phone,
                goods_code=goods_code,
                callback_no=GIFTISHOW_CALLBACK_NO,
                gubun="I",  # 바코드이미지 수신 — PIN + 이미지URL
                mms_title="경품",
                mms_msg="축하합니다!",
            )

            # 규격서 기준 중첩 응답 파싱
            parsed = GiftishowClient.parse_send_response(resp)

            if parsed["outer_code"] == "0000" and parsed["inner_code"] == "0000":
                success += 1
                db.update_winner_send_result(
                    order_id, tid,
                    send_status="SENT",
                    tr_id=tr_id,
                    response_code=parsed["inner_code"],
                    response_message=parsed["inner_message"] or "성공",
                    coupon_pin=parsed["pin_no"],
                    coupon_img_url=parsed["coupon_img_url"],
                    order_no=parsed["order_no"],
                )

                # === 텔레그램 DM으로 쿠폰 전달 (카카오톡 대신) ===
                try:
                    # 바코드 이미지 전송
                    if parsed["coupon_img_url"]:
                        await context.bot.send_photo(
                            chat_id=tid,
                            photo=parsed["coupon_img_url"],
                            caption="🎁 기프티콘 교환 바코드",
                        )
                    # PIN 번호 + 안내 메시지
                    dm_lines = ["🎁 <b>기프티콘이 도착했습니다!</b>", ""]
                    if parsed["pin_no"]:
                        dm_lines.append(f"PIN: <code>{parsed['pin_no']}</code>")
                    dm_lines.append("")
                    dm_lines.append("⚠️ 유효기간 30일 | 기간연장·환불 불가")
                    dm_lines.append("인지세 삼성 세무서장 후납승인 2019년 100007555호")
                    await context.bot.send_message(
                        chat_id=tid,
                        text="\n".join(dm_lines),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass  # DM 실패해도 쿠폰 자체는 발행됨
            else:
                fail += 1
                msg = parsed["inner_message"] or parsed["outer_message"] or ""
                db.update_winner_send_result(
                    order_id, tid,
                    send_status="FAILED",
                    tr_id=tr_id,
                    response_code=parsed["inner_code"] or parsed["outer_code"],
                    response_message=msg,
                )
        except Exception as e:
            # 타임아웃 등 — 먼저 sendFail/cancel 시도 후 일반 cancel 시도
            try:
                client.cancel_send_fail(tr_id)
            except Exception:
                try:
                    client.cancel_coupon(tr_id)
                except Exception:
                    pass
            fail += 1
            db.update_winner_send_result(
                order_id, tid,
                send_status="ERROR",
                tr_id=tr_id,
                response_code="EX",
                response_message=str(e)[:200],
            )

    status = "SENT" if fail == 0 else ("PARTIAL" if success > 0 else "FAILED")
    db.set_order_status(order_id, status)
    await context.bot.send_message(
        chat_id=order["admin_telegram_id"],
        text=f"📦 발송 완료\n주문: {order_id}\n성공: {success}\n실패: {fail}\n상태: {status}",
    )


# ==================== Order History ====================

async def show_orders(q, context):
    if not is_admin(q.from_user.id):
        await q.edit_message_text("관리자만 가능합니다.")
        return
    orders = db.list_orders_for_admin(q.from_user.id, 10)
    if not orders:
        await q.edit_message_text("주문내역이 없습니다.", reply_markup=admin_menu())
        return
    lines = ["📑 <b>최근 주문</b>", ""]
    kb = []
    for o in orders:
        lines.append(f"- <code>{o['order_id']}</code> | {o['status']} | {int(o['total_price']):,}원")
        kb.append([InlineKeyboardButton(o["order_id"], callback_data=f"{CB_ORDER}:{o['order_id']}")])
    kb.append([InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


async def on_order_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    order_id = q.data.split(":", 1)[1]
    order = db.get_order(order_id)
    if not order:
        await q.edit_message_text("주문을 찾을 수 없습니다.", reply_markup=admin_menu())
        return
    if (q.from_user.id != int(order["admin_telegram_id"])) and (not is_super(q.from_user.id)):
        await q.edit_message_text("이 주문을 조회할 권한이 없습니다.", reply_markup=admin_menu())
        return
    winners = db.list_order_winners(order_id)
    lines = [
        "🧾 <b>주문 상세</b>",
        f"주문번호: <code>{order_id}</code>",
        f"상태: <b>{order['status']}</b>",
        f"금액: <b>{int(order['total_price']):,}원</b>",
        f"수령자: {len(winners)}명",
    ]
    for w in winners[:20]:
        lines.append(f"- @{w['winner_username']} | {w['send_status']}")
    if len(winners) > 20:
        lines.append(f"...(+{len(winners)-20})")
    await q.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ 주문목록", callback_data=f"{CB_MENU}:orders")],
            [InlineKeyboardButton("🏠 메뉴", callback_data=f"{CB_MENU}:home")],
        ]),
    )


# ==================== Misc ====================

async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.answer()
    except BadRequest:
        pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, BadRequest) and ("Query is too old" in str(err) or "query id is invalid" in str(err)):
        return
    print("Unhandled error:", repr(err))


# ==================== Main ====================

def get_app():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing in .env")
    db.init_db()
    seed = os.path.join(os.path.dirname(__file__), "products_seed.json")
    if os.path.exists(seed):
        db.seed_products_from_json(seed)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler("balance", cmd_balance))

    # Phase 3 Event Handlers
    from app.event_manager import cmd_create_event, cmd_draw_event, CB_JOIN_EVENT, on_join_event
    app.add_handler(CommandHandler("event", cmd_create_event))
    app.add_handler(CommandHandler("draw", cmd_draw_event))
    app.add_handler(CallbackQueryHandler(on_join_event, pattern=f"^{CB_JOIN_EVENT}:"))

    app.add_handler(CallbackQueryHandler(on_menu, pattern=f"^{CB_MENU}:"))
    app.add_handler(CallbackQueryHandler(on_catalog, pattern=f"^{CB_CATALOG}:"))
    app.add_handler(CallbackQueryHandler(on_qty, pattern=f"^{CB_QTY}:"))
    app.add_handler(CallbackQueryHandler(on_qtyin, pattern=f"^{CB_QTYIN}:"))
    app.add_handler(CallbackQueryHandler(on_cart, pattern=f"^{CB_CART}:"))
    app.add_handler(CallbackQueryHandler(on_clear, pattern=f"^{CB_CLEAR}:"))
    app.add_handler(CallbackQueryHandler(on_checkout_start, pattern=f"^{CB_CHECKOUT}:start$"))
    app.add_handler(CallbackQueryHandler(on_checkout_action, pattern=f"^{CB_CHECKOUT}:(create|retry)$"))
    app.add_handler(CallbackQueryHandler(on_paid, pattern=f"^{CB_PAID}:"))
    app.add_handler(CallbackQueryHandler(on_approve_reject, pattern=f"^({CB_APPROVE}|{CB_REJECT}):"))
    app.add_handler(CallbackQueryHandler(on_order_view, pattern=f"^{CB_ORDER}:"))
    app.add_handler(CallbackQueryHandler(noop, pattern="^noop$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_router))
    return app


def main():
    app_instance = get_app()
    app_instance.run_polling()


if __name__ == "__main__":
    main()
