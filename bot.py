import os
import asyncio
from telegram import (
	Update,
	User,
	InlineKeyboardButton,
	InlineKeyboardMarkup,
	BotCommand,
	MenuButtonCommands
)
from telegram.ext import (
	Application,
	ApplicationBuilder,
	CallbackContext,
	ContextTypes,
	CommandHandler,
	MessageHandler,
	CallbackQueryHandler,
	AIORateLimiter,
	filters
)
from telegram.constants import ParseMode, ChatAction
from wallet import target_wallet, my_wallet
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
HELP_MESSAGE = """Commands:
⚪ /get_my_balance – Show my balance
⚪ /get_my_positions – Show my positions
⚪ /get_target_positions – Show target positions
⚪ /set_target_address – Set new target address
⚪ /switch_on – Start copy trading
⚪ /switch_off – End copy trading
⚪ /help – Show help
"""
# /send_msg - Send Telegram Message

application = Application.builder().token(TELEGRAM_TOKEN).build()

async def post_init(application: Application):
	await application.bot.set_my_commands([
		BotCommand("/get_my_balance", "Show my balance"),
		BotCommand("/get_my_positions", "Show my positions"),
		BotCommand("/get_target_positions", "Show target positions"),
		BotCommand("/set_target_address", "Set new target address"),
		BotCommand("/switch_on", "Start copy trading"),
		BotCommand("/switch_off", "End copy trading"),
		BotCommand("/help", "Show help message"),
		# BotCommand("/send_msg", "Send Telegram Message")
	])

async def send_telegram_message(message):
	try:
		await application.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message)
		# print(f"Telegram message sent: {message}")
	except Exception as e:
		print(f"Error sending Telegram message: {e}")

# async def send_msg_handle(update: Update, context: CallbackContext):
# 	await send_telegram_message("Hi")

async def start_handle(update: Update, context: CallbackContext):
	# await register_user_if_not_exists(update, context, update.message.from_user)
	# user_id = update.message.from_user.id
	reply_text = "Welcome to Hyperliquid Copy Trading\n\n"
	reply_text += HELP_MESSAGE
	reply_text += "\nHappy Trading!"

	await update.message.reply_text(reply_text)

async def help_handle(update: Update, context: CallbackContext):
	keyboard = [
		[
			InlineKeyboardButton("switchOn", callback_data="switch_on"),
			InlineKeyboardButton("switchOff", callback_data="switch_off"),
		],
		[
			InlineKeyboardButton("GetMyPositions", callback_data="get_my_positions"),
			InlineKeyboardButton("GetTargetPositions", callback_data="get_target_positions"),
		],
		[
			InlineKeyboardButton("setTargetAddress", callback_data="set_target_address"),
			
		],
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(HELP_MESSAGE, reply_markup=reply_markup)

async def get_my_balance_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(my_wallet.asset)

async def get_my_positions_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(my_wallet.positions)

async def get_target_positions_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(target_wallet.positions)

async def set_target_address_handle(update: Update, context: CallbackContext, value=None):
	if value is None:        
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text("Please reply with the target address")
		context.user_data['awaiting'] = 'set_target_address'
		return
	try:
		print(f"old address: {target_wallet.address}")
		print(f"new address: {value}")
		target_wallet.set_address(value)
		message = f"Target Wallet Address set to {value}"
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text(message)
	except ValueError:
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text("Invalid value. Usage: Reply with a number (e.g., 0.6)")

async def switch_on_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, value=True):
	await set_trade_mode(update, value)

async def switch_off_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, value=False):
	await set_trade_mode(update, value)

async def set_trade_mode(update, value=None):
	mod = "ON" if value else "OFF"
	try:
		my_wallet.set_mode(value)
		message = f"Trade mode is {mod}"
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text(message)
	except ValueError:
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text(f"Failed to switch {mod} trade mode")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	command = query.data

	command_map = {
		"help": help_handle,
		"get_my_balance": get_my_balance_handle,
		"get_my_positions": get_my_positions_handle,
		"get_target_positions": get_target_positions_handle,
		"set_target_address": set_target_address_handle,
		"switch_on": switch_on_handle,
		"switch_off": switch_off_handle,
	}

	if command in command_map:
		await command_map[command](update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if 'awaiting' in context.user_data:
		command = context.user_data.pop('awaiting')
		command_map = {
			"set_target_address": set_target_address_handle,
		}
		if command in command_map:
			await command_map[command](update, context, value=update.message.text)

def add_all_handlers():
	application.add_handler(CommandHandler("start", start_handle))
	application.add_handler(CommandHandler("help", help_handle))
	application.add_handler(CommandHandler("get_my_balance", get_my_balance_handle))
	application.add_handler(CommandHandler("get_my_positions", get_my_positions_handle))
	application.add_handler(CommandHandler("get_target_positions", get_target_positions_handle))
	application.add_handler(CommandHandler("set_target_address", set_target_address_handle))
	application.add_handler(CommandHandler("switch_on", switch_on_handle))
	application.add_handler(CommandHandler("switch_off", switch_off_handle))  
	# application.add_handler(CommandHandler("send_msg", send_msg_handle)) 
	application.add_handler(CallbackQueryHandler(callback_query_handler))
	application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
	
async def keep_alive_silent():
	while True:
		await asyncio.sleep(900)  # 15 minutes
		try:
			await application.bot.get_me()  # Silent API call to keep connection alive
		except Exception as e:
			print(f"Silent keep-alive error: {e}")

async def start_bot():
	add_all_handlers()
	
	print("Starting Telegram bot polling...")
	await application.initialize()
	await application.start()
	await post_init(application)
	
	while True:
		# Start Telegram Bot
		try:
			await application.updater.start_polling(
				timeout=30,
				drop_pending_updates=True,
				poll_interval=1.0
			)
			# Start keep-alive task
			asyncio.create_task(keep_alive_silent())
			print("application started")
			break  # Exit retry loop if polling starts successfully
		except Exception as e:
			message = f"Polling error: {e}. Retrying in 5 seconds..."
			await send_telegram_message(message)
			print(message)
			await asyncio.sleep(5)
	
	# add_all_handlers()
	# print("Starting Telegram bot polling...")

	# await application.initialize()
	# await application.start()
	# await application.updater.start_polling(
	#     drop_pending_updates=True,
	#     poll_interval=1.0,
	#     timeout=30
	# )
	# asyncio.create_task(keep_alive_silent())
	# print("Telegram bot is running.")
	# # DO NOT RETURN — let it run forever
	# await asyncio.Future()  # Keeps task alive