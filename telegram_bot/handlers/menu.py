import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from backend.services.supabase_service import (
    create_user_if_not_exists,
    get_db,
    create_order,
    get_unused_credential
)
from telegram_bot.services.razorpay_service import create_payment_link, IS_DEV_MODE

logger = logging.getLogger(__name__)

# Main Menu Layout
def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📺 OTT Subscriptions", callback_data="cat_OTT"),
            InlineKeyboardButton("🎮 Game Accounts", callback_data="cat_Games")
        ],
        [
            InlineKeyboardButton("📜 Order History", callback_data="view_history"),
            InlineKeyboardButton("ℹ️ Support / Help", callback_data="view_support")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user = update.effective_user
    logger.info(f"User {user.id} started the bot.")
    
    # Save user to DB
    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    banner = (
        f"⚡ <b>WELCOME TO ELITE DIGITAL STORE</b> ⚡\n\n"
        f"Hello {user.first_name}! We provide 100% automated instant delivery of gaming credentials and premium OTT services.\n\n"
        f"📦 <b>Instant Delivery:</b> Game accounts (Steam, Valorant, GTA V, etc.)\n"
        f"⚙️ <b>Fast Setup:</b> OTT subscriptions (Netflix, Spotify, YouTube Premium, etc.)\n\n"
        f"👇 <i>Select a category below to browse our inventory:</i>"
    )

    await update.message.reply_text(
        text=banner,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes all inline button clicks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user
    supabase = get_db()

    if data == "main_menu":
        banner = (
            f"⚡ <b>ELITE DIGITAL STORE - MAIN MENU</b> ⚡\n\n"
            f"Browse our high-quality inventory using the buttons below:"
        )
        await query.edit_message_text(
            text=banner,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )

    elif data.startswith("cat_"):
        category = data.split("_")[1]
        
        # Fetch active products in this category
        try:
            response = supabase.table("products").select("*").eq("category", category).eq("active", True).execute()
            products = response.data
        except Exception as e:
            logger.error(f"Error fetching products: {str(e)}")
            products = []

        if not products:
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
            await query.edit_message_text(
                text=f"🗂️ <b>Category: {category}</b>\n\nCurrently, there are no active products in this category. Please check back later!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

        keyboard = []
        # Create grid of products
        for prod in products:
            keyboard.append([
                InlineKeyboardButton(
                    f"{prod['name']} - ₹{float(prod['price']):.2f}", 
                    callback_data=f"prod_{prod['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])

        await query.edit_message_text(
            text=f"🗂️ <b>Browse {category} Products:</b>\n\nChoose a product below to view details and buy:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data.startswith("prod_"):
        product_id = data.split("_")[1]
        
        try:
            response = supabase.table("products").select("*").eq("id", product_id).execute()
            product = response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching product detail: {str(e)}")
            product = None

        if not product:
            await query.edit_message_text(
                text="❌ Product not found. It may have been disabled or deleted by the admin.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]),
                parse_mode="HTML"
            )
            return

        # Check stock availability
        is_in_stock = False
        stock_label = ""
        
        try:
            stock_resp = supabase.table("credentials").select("id").eq("product_id", product["id"]).eq("status", "UNUSED").execute()
            stock_count = len(stock_resp.data) if stock_resp.data else 0
        except Exception as e:
            logger.error(f"Error checking stock: {str(e)}")
            stock_count = 0

        is_in_stock = stock_count > 0
        stock_label = f"✅ In Stock ({stock_count} available)" if is_in_stock else "❌ OUT OF STOCK"

        details = (
            f"📦 <b>PRODUCT DETAIL</b> 📦\n\n"
            f"🏷️ <b>Name:</b> {product['name']}\n"
            f"🗂️ <b>Category:</b> {product['category']}\n"
            f"💰 <b>Price:</b> ₹{float(product['price']):.2f}\n"
            f"⚡ <b>Delivery:</b> ✨ INSTANT AUTO-DELIVERY ✨\n"
            f"📊 <b>Stock:</b> {stock_label}\n\n"
        )

        if is_in_stock:
            details += f"🛒 <i>Ready to purchase? Click 'Buy Now' to generate a secure Razorpay checkout link:</i>"
            keyboard = [
                [InlineKeyboardButton("💳 Buy Now (Generate Link)", callback_data=f"buy_{product['id']}")],
                [InlineKeyboardButton(f"🔙 Back to {product['category']}", callback_data=f"cat_{product['category']}")]
            ]
        else:
            details += f"⚠️ <i>This product is currently out of stock. Please check back later or contact support.</i>"
            keyboard = [
                [InlineKeyboardButton(f"🔙 Back to {product['category']}", callback_data=f"cat_{product['category']}")]
            ]

        await query.edit_message_text(
            text=details,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data.startswith("buy_"):
        product_id = data.split("_")[1]
        
        await query.edit_message_text("⏳ <i>Checking stock & generating payment link, please wait...</i>", parse_mode="HTML")

        try:
            response = supabase.table("products").select("*").eq("id", product_id).execute()
            product = response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error checking product: {str(e)}")
            product = None

        if not product:
            await query.edit_message_text("❌ Product not found.")
            return

        # ⚠️ STOCK CHECK: Verify credentials exist before accepting payment
        has_stock = False
        try:
            stock_check = supabase.table("credentials").select("id").eq("product_id", product_id).eq("status", "UNUSED").limit(1).execute()
            has_stock = bool(stock_check.data)
        except Exception as e:
            logger.error(f"Stock check failed: {str(e)}")
            has_stock = False

        if not has_stock:
            await query.edit_message_text(
                text=(
                    f"❌ <b>OUT OF STOCK!</b>\n\n"
                    f"Sorry, <b>{product['name']}</b> is currently out of stock. "
                    f"No credentials are available for delivery right now.\n\n"
                    f"Please check back later or contact support for restocking updates."
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
            return

        price = float(product["price"])
        
        # Create Razorpay payment link
        pay_res = await create_payment_link(
            amount=price,
            product_name=product["name"],
            telegram_id=user.id,
            product_id=product["id"],
            first_name=user.first_name
        )

        if not pay_res.get("success"):
            await query.edit_message_text(
                text=f"❌ <b>Error generating payment link:</b>\n<code>{pay_res.get('error')}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]),
                parse_mode="HTML"
            )
            return

        payment_id = pay_res["payment_link_id"]
        short_url = pay_res["short_url"]

        # Save order as PENDING in database
        create_order(
            telegram_id=user.id,
            product_id=product["id"],
            payment_id=payment_id,
            amount=price
        )

        checkout_text = (
            f"🛒 <b>CHECKOUT DETAILS</b> 🛒\n\n"
            f"📦 <b>Item:</b> {product['name']}\n"
            f"💰 <b>Amount Due:</b> ₹{price:.2f}\n"
            f"🆔 <b>Order Reference:</b> <code>{payment_id}</code>\n\n"
            f"🔐 Click the button below to pay securely via Razorpay. "
            f"Once you complete the payment, the transaction is verified instantly by our webhooks."
        )

        keyboard = [
            [InlineKeyboardButton("💳 Pay Securely (Razorpay)", url=short_url)],
            [InlineKeyboardButton("❌ Cancel Order", callback_data="main_menu")]
        ]
        
        # Only show test payment button in development mode
        if IS_DEV_MODE:
            keyboard.insert(1, [InlineKeyboardButton("🧪 Test Payment (Dev Only)", callback_data=f"simulate:{payment_id}:{int(price*100)}")])

        await query.edit_message_text(
            text=checkout_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data.startswith("simulate:"):
        # Simulated payment for local dev testing
        parts = data.split(":")
        payment_id = parts[1]
        amount_paise = int(parts[2])
        
        await query.edit_message_text("⏳ <i>Processing test payment...</i>", parse_mode="HTML")
        
        import httpx
        import json
        import hmac
        import hashlib
        try:
            payload = {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": payment_id,
                            "order_id": payment_id,
                            "amount": amount_paise
                        }
                    }
                }
            }
            
            payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
            signature = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest() if secret else "dev_mock_signature"

            async with httpx.AsyncClient() as client:
                backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
                resp = await client.post(
                    f"{backend_url}/webhook/razorpay", 
                    content=payload_bytes, 
                    headers={
                        "X-Razorpay-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )
                
                if resp.status_code == 200:
                    await query.edit_message_text(
                        "✅ <b>Payment Verified!</b>\n\nYour order has been processed. Check this chat for delivery details.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]),
                        parse_mode="HTML"
                    )
                else:
                    await query.edit_message_text(
                        f"❌ <b>Payment processing failed.</b>\n\nBackend returned status {resp.status_code}. Make sure the server is running.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]),
                        parse_mode="HTML"
                    )
        except Exception as e:
            await query.edit_message_text(
                f"❌ <b>Connection Error</b>\n\nCould not reach the backend server.\n<code>{str(e)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]),
                parse_mode="HTML"
            )

    elif data == "view_history":
        try:
            # Query user orders
            response = supabase.table("orders").select("*, products(*)").eq("telegram_id", user.id).eq("status", "COMPLETED").order("created_at", desc=True).execute()
            orders = response.data
        except Exception as e:
            logger.error(f"Error fetching order history: {str(e)}")
            orders = []

        if not orders:
            await query.edit_message_text(
                text="📜 <b>Order History</b>\n\nYou haven't made any purchases yet. Start shopping now!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]),
                parse_mode="HTML"
            )
            return

        history_text = "📜 <b>YOUR COMPLETED ORDERS:</b>\n\n"
        for idx, order in enumerate(orders[:10], 1): # Show latest 10
            prod = order["products"]
            status = "Delivered" if order["delivery_status"] == "DELIVERED" else "Pending Setup"
            history_text += f"{idx}. <b>{prod['name']}</b>\n   💰 ₹{float(order['amount']):.2f} | 📅 {order['created_at'][:10]}\n   🚚 Status: {status}\n\n"
            
        await query.edit_message_text(
            text=history_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]),
            parse_mode="HTML"
        )

    elif data == "view_support":
        support_text = (
            f"ℹ️ <b>CUSTOMER SUPPORT</b> ℹ️\n\n"
            f"Have issues with a digital product or payment? We are here to help!\n\n"
            f"👤 <b>Admin Contact:</b> @Ramaon_dino\n\n"
            f"<i>Please share your Order Reference ID while contacting support for quick resolution.</i>"
        )
        keyboard = [
            [InlineKeyboardButton("💬 Chat with Admin", url="https://t.me/Ramaon_dino")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            text=support_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data == "write_review":
        context.user_data['awaiting_review'] = True
        review_text = (
            f"🌟 <b>We value your feedback!</b> 🌟\n\n"
            f"Please type your review below and send it to me. Your reviews help us improve our services!"
        )
        await query.edit_message_text(
            text=review_text,
            parse_mode="HTML"
        )

