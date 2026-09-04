# -*- coding: utf-8 -*-
"""
Telegram-бот "Интернет-магазин" на python-telegram-bot v20+

Установка:
    pip install python-telegram-bot==21.*

Запуск:
    1. Получите токен у @BotFather
    2. Вставьте его в переменную BOT_TOKEN ниже (или через переменную окружения)
    3. python bot.py
"""

import logging
import os
from dataclasses import dataclass

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "8921387718:AAG4pThUlb9sDdpo1S106n-T2EnOZPfC46Y")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Каталог товаров
# ---------------------------------------------------------------------------

@dataclass
class Product:
    id: str
    title: str
    price: int  # в рублях
    description: str
    emoji: str


CATALOG: dict[str, Product] = {
    "tshirt": Product(
        id="tshirt",
        title="Футболка «Кодер»",
        price=1200,
        description="Хлопковая футболка с забавным принтом про программирование. Размеры S–XL.",
        emoji="👕",
    ),
    "mug": Product(
        id="mug",
        title="Кружка «Debug Mode»",
        price=650,
        description="Керамическая кружка 350 мл. Идеальна для кофе во время дедлайна.",
        emoji="☕",
    ),
    "notebook": Product(
        id="notebook",
        title="Блокнот разработчика",
        price=450,
        description="Блокнот в клетку А5 с разметкой под UML-диаграммы и todo-листы.",
        emoji="📓",
    ),
}

# in-memory "БД" корзин: {user_id: {product_id: qty}}
CARTS: dict[int, dict[str, int]] = {}

# in-memory история заказов: {user_id: [order, ...]}
ORDERS: dict[int, list[dict]] = {}

# состояния ConversationHandler для оформления заказа
ASK_NAME, ASK_ADDRESS, ASK_PHONE = range(3)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def get_cart(user_id: int) -> dict[str, int]:
    return CARTS.setdefault(user_id, {})


def cart_total(user_id: int) -> int:
    cart = get_cart(user_id)
    return sum(CATALOG[pid].price * qty for pid, qty in cart.items())


def format_cart(user_id: int) -> str:
    cart = get_cart(user_id)
    if not cart:
        return "Корзина пуста 🛒"
    lines = ["🛒 <b>Ваша корзина:</b>\n"]
    for pid, qty in cart.items():
        p = CATALOG[pid]
        lines.append(f"{p.emoji} {p.title} — {qty} шт. × {p.price}₽ = {p.price * qty}₽")
    lines.append(f"\n💰 <b>Итого: {cart_total(user_id)}₽</b>")
    return "\n".join(lines)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🛍 Каталог", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="orders")],
    ]
    return InlineKeyboardMarkup(keyboard)


def catalog_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    for p in CATALOG.values():
        keyboard.append(
            [InlineKeyboardButton(f"{p.emoji} {p.title} — {p.price}₽", callback_data=f"product:{p.id}")]
        )
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)


def product_keyboard(pid: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"add:{pid}")],
        [InlineKeyboardButton("⬅️ К каталогу", callback_data="catalog")],
    ]
    return InlineKeyboardMarkup(keyboard)


def cart_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard = []
    cart = get_cart(user_id)
    for pid in cart:
        p = CATALOG[pid]
        keyboard.append(
            [
                InlineKeyboardButton(f"➖ {p.title}", callback_data=f"remove:{pid}"),
                InlineKeyboardButton(f"➕ {p.title}", callback_data=f"add:{pid}"),
            ]
        )
    if cart:
        keyboard.append([InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)


# ---------------------------------------------------------------------------
# Хендлеры команд
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 Добро пожаловать в наш интернет-магазин!\n\n"
        "Здесь вы найдёте три отличных товара для разработчиков.\n"
        "Выберите раздел ниже:"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ <b>Доступные команды:</b>\n"
        "/start — открыть главное меню\n"
        "/catalog — посмотреть товары\n"
        "/cart — открыть корзину\n"
        "/help — эта справка"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🛍 <b>Каталог товаров:</b>", parse_mode=ParseMode.HTML,
                                     reply_markup=catalog_keyboard())


async def cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        format_cart(user_id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(user_id)
    )


# ---------------------------------------------------------------------------
# Хендлер кнопок (callback_query)
# ---------------------------------------------------------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "menu":
        await query.edit_message_text(
            "👋 Главное меню интернет-магазина. Выберите раздел:",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "catalog":
        await query.edit_message_text(
            "🛍 <b>Каталог товаров:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=catalog_keyboard(),
        )

    elif data.startswith("product:"):
        pid = data.split(":", 1)[1]
        p = CATALOG[pid]
        text = f"{p.emoji} <b>{p.title}</b>\n\n{p.description}\n\n💰 Цена: {p.price}₽"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=product_keyboard(pid))

    elif data.startswith("add:"):
        pid = data.split(":", 1)[1]
        cart = get_cart(user_id)
        cart[pid] = cart.get(pid, 0) + 1
        await query.answer(f"Добавлено: {CATALOG[pid].title}", show_alert=False)
        # Если добавляли из карточки товара — остаёмся там, иначе обновляем корзину
        if query.message.text and "Ваша корзина" in query.message.text or data:
            await query.edit_message_text(
                format_cart(user_id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(user_id)
            )

    elif data.startswith("remove:"):
        pid = data.split(":", 1)[1]
        cart = get_cart(user_id)
        if pid in cart:
            cart[pid] -= 1
            if cart[pid] <= 0:
                del cart[pid]
        await query.edit_message_text(
            format_cart(user_id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(user_id)
        )

    elif data == "cart":
        await query.edit_message_text(
            format_cart(user_id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(user_id)
        )

    elif data == "clear":
        CARTS[user_id] = {}
        await query.edit_message_text(
            format_cart(user_id), parse_mode=ParseMode.HTML, reply_markup=cart_keyboard(user_id)
        )

    elif data == "orders":
        user_orders = ORDERS.get(user_id, [])
        if not user_orders:
            text = "У вас пока нет заказов 📭"
        else:
            lines = ["📦 <b>Ваши заказы:</b>\n"]
            for i, order in enumerate(user_orders, start=1):
                lines.append(f"№{i} — {order['total']}₽, получатель: {order['name']}")
            text = "\n".join(lines)
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())

    elif data == "checkout":
        if not get_cart(user_id):
            await query.answer("Корзина пуста!", show_alert=True)
            return
        await query.edit_message_text(
            "📝 Оформление заказа.\n\nКак к вам обращаться? Введите имя:"
        )
        context.user_data["checkout_stage"] = ASK_NAME


# ---------------------------------------------------------------------------
# ConversationHandler для оформления заказа (сбор имени, адреса, телефона)
# ---------------------------------------------------------------------------

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    if not get_cart(update.effective_user.id):
        await update.callback_query.edit_message_text(
            "Корзина пуста!", reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    await update.callback_query.edit_message_text("📝 Как к вам обращаться? Введите имя:")
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["order_name"] = update.message.text
    await update.message.reply_text("🏠 Введите адрес доставки:")
    return ASK_ADDRESS


async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["order_address"] = update.message.text
    await update.message.reply_text("📱 Введите номер телефона для связи:")
    return ASK_PHONE


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    context.user_data["order_phone"] = update.message.text

    order = {
        "name": context.user_data.get("order_name"),
        "address": context.user_data.get("order_address"),
        "phone": context.user_data.get("order_phone"),
        "items": dict(get_cart(user_id)),
        "total": cart_total(user_id),
    }
    ORDERS.setdefault(user_id, []).append(order)
    CARTS[user_id] = {}  # очищаем корзину после оформления

    text = (
        "✅ <b>Заказ оформлен!</b>\n\n"
        f"👤 Имя: {order['name']}\n"
        f"🏠 Адрес: {order['address']}\n"
        f"📱 Телефон: {order['phone']}\n"
        f"💰 Сумма: {order['total']}₽\n\n"
        "Спасибо за покупку! Мы свяжемся с вами для подтверждения."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def cancel_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Оформление заказа отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    if BOT_TOKEN == "ВСТАВЬТЕ_СЮДА_ВАШ_ТОКЕН":
        raise SystemExit(
            "Ошибка: укажите токен бота в переменной BOT_TOKEN "
            "(в коде или через переменную окружения BOT_TOKEN)."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    # Обычные команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("catalog", catalog_command))
    application.add_handler(CommandHandler("cart", cart_command))

    # Диалог оформления заказа
    checkout_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(checkout_start, pattern="^checkout$")],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel_checkout)],
    )
    application.add_handler(checkout_conv)

    # Остальные inline-кнопки (каталог, корзина, добавление товаров и т.д.)
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

