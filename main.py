import logging
import asyncio
from telegram import ReplyKeyboardMarkup
from selenium.webdriver import Keys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from selenium.webdriver.chrome.options import Options
import json
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
# Этапы диалога
ASK_UID, ASK_VERIFICATION, ASK_CODE = range(3)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7928841741:AAGCeKPeAyIVVTOAq2aZFcadi7_sHQDtdhA"  # Замените на ваш токен

USERS_FILE = "users.json"


async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["verification"] = update.message.text.strip()

    with open("Codes.json", "r") as f:
        codes_data = json.load(f)
        codes = codes_data.get("codes", [])

    await update.message.reply_text("⏳ Ввожу коды, пожалуйста подожди...")

    uid = context.user_data["uid"]
    verification = context.user_data["verification"]

    result = await asyncio.to_thread(redeem_code, uid, verification, codes)
    await update.message.reply_text(f"✅ Готово!\n\n{result}")

    return ConversationHandler.END

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (json.decoder.JSONDecodeError, FileNotFoundError):
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def save_user_uid(user_id, uid):
    users = load_users()
    user_data = users.get(user_id, {"uids": {}})
    user_data["uids"][uid] = {}
    users[user_id] = user_data
    save_users(users)

def get_user_uids(user_id):
    users = load_users()
    return list(users.get(user_id, {}).get("uids", {}).keys())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    context.user_data["user_id"] = user_id

    uids = get_user_uids(user_id)

    if uids:
        reply_keyboard = [[uid] for uid in uids] + [["Добавить новый UID"]]
        await update.message.reply_text(
            "Выбери один из своих UID или добавь новый:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return ASK_UID  # используем это состояние как выбор UID
    else:
        await update.message.reply_text("Привет! Введи свой UID из игры AFK Arena:")
        return ASK_VERIFICATION

async def ask_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.message.text.strip()
    context.user_data["uid"] = uid

    save_user_uid(context.user_data["user_id"], uid)

    await update.message.reply_text("Теперь введи код подтверждения:")
    return ASK_CODE

async def ask_uid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "Добавить новый UID":
        await update.message.reply_text("Введи новый UID:")
        return ASK_VERIFICATION
    else:
        context.user_data["uid"] = text
        await update.message.reply_text("Теперь введи код подтверждения:")
        return ASK_CODE

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["code"] = update.message.text.strip()

    uid = context.user_data["uid"]
    verification = context.user_data["verification"]
    code = context.user_data["code"]

    await update.message.reply_text(f"Пробую активировать код `{code}`...")

    result = await asyncio.to_thread(redeem_code, uid, verification, code)
    await update.message.reply_text(f"Результат: {result}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

async def redeem_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    uid = get_user_uids(user_id)

    if not uid:
        await update.message.reply_text("Пожалуйста, сначала отправьте свой UID с помощью команды /start.")
        return

    context.user_data["uid"] = uid
    await update.message.reply_text("Введите код подтверждения из игры:")
    return ASK_CODE  # Переход к шагу, где пользователь вводит verification code

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Инструкция по использованию бота:*\n\n"
        "/start — начать или продолжить регистрацию\n"
        "/redeemcodes — активировать все коды из файла `gift_codes.json`\n"
        "/cancel — отменить текущую операцию\n"
        "/help — показать эту справку"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


def redeem_code(uid, verification_code, gift_code):
    options = Options()
    options.add_argument("--headless")  # обязательный для Railway
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.binary_location = "/usr/bin/chromium"  # chromium в Docker

    # инициализация драйвера
    driver = webdriver.Chrome(options=options)

    try:
        wait = WebDriverWait(driver, 10)
        driver.get("https://cdkey.lilith.com/afk-global")

        print("[+] Нажимаем на 'Companions'")
        companions_radio = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='radio'][value='group']")))
        driver.execute_script("arguments[0].click();", companions_radio)

        print("[+] Вводим UID")
        uid_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter Text']")))
        uid_input.send_keys(uid)

        print("[+] Вводим Verification Code")
        verification_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter Verification Code']")))
        verification_input.send_keys(verification_code)

        print("[+] Нажимаем 'Log In'")
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn___1N4RM")))
        login_button.click()

        print("[*] Ждём появления поля Gift Code")
        time.sleep(3)  # можно заменить на более точное ожидание, но этого обычно хватает

        print("[+] Вводим Gift Code")
        gift_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter Gift Code']")))
        gift_input.send_keys(gift_code)

        print("[+] Нажимаем 'Redeem'")
        redeem_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "exchangeBtn___2mrmp")))
        redeem_button.click()

        print("[✅] Успешно!")
        return "Успешно активировано!"

    except Exception as e:
        print("[❌] Ошибка:", e)
        return f"Ошибка: {e}"

    finally:
        driver.quit()

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("redeemcodes", redeem_codes_command),
        ],
        states={
            ASK_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_uid_choice)],
            ASK_VERIFICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_verification)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))  # <--- Добавляем /help

    application.run_polling()

if __name__ == "__main__":
    main()
