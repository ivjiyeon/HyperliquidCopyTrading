import os
import asyncio
import threading
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
from telegram.error import NetworkError, TimedOut
# from telegram.constants import ParseMode, ChatAction
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


async def post_init():
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

def send_telegram_message(message):
	try:
		asyncio.run_coroutine_threadsafe(
			application.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message),
			bot_event_loop
		)
	except Exception as e:
		print(f"Error sending Telegram message: {e}")

async def get_pair(update: Update, context: ContextTypes.DEFAULT_TYPE, command):
	buttons = []
	for name in pairs_data.keys():
		buttons.append([InlineKeyboardButton(name, callback_data=name)])

	keyboard = InlineKeyboardMarkup(buttons)
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(
		"Which wallet do you want to check?",
		reply_markup=keyboard
	)
	context.user_data["command"] = command

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
			InlineKeyboardButton("SwitchOn", callback_data="switch_on"),
			InlineKeyboardButton("SwitchOff", callback_data="switch_off"),
		],
		[
			InlineKeyboardButton("GetMyPositions", callback_data="get_my_positions"),
			InlineKeyboardButton("GetTargetPositions", callback_data="get_target_positions"),
		],
		[
			InlineKeyboardButton("GetMyBalance", callback_data="get_my_balance"),
			InlineKeyboardButton("SetTargetAddress", callback_data="set_target_address"),			
		],
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(HELP_MESSAGE, reply_markup=reply_markup)

async def get_my_balance_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, pair=None):
	if pair is None:
		await get_pair(update, context, "get_my_balance")
		return
	pair.my_wallet.update_user_state()
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(pair.my_wallet.asset)

async def get_my_positions_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, pair=None):
	if pair is None:
		await get_pair(update, context, "get_my_positions")
		return
	pair.my_wallet.update_user_state()
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(pair.my_wallet.positions)

async def get_target_positions_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, pair=None):
	if pair is None:
		await get_pair(update, context, "get_target_positions")
		return
	pair.target_wallet.update_user_state()
	msg = update.callback_query.message if update.callback_query else update.message
	await msg.reply_text(pair.target_wallet.positions)

async def set_target_address_handle(update: Update, context: CallbackContext, value=None, pair=None):
	if pair is None:
		await get_pair(update, context, "get_my_balance")
		return
	if value is None:        
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text("Please reply with the target address")
		context.user_data['awaiting'] = 'set_target_address'
		context.user_data['pair'] = pair
		return
	try:
		print(f"old address: {pair.target_wallet.address}")
		print(f"new address: {value}")
		pair.target_wallet.set_address(value)
		message = f"Target Wallet Address set to {value}"
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text(message)
	except ValueError:
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text("Invalid value. Usage: Reply with a number (e.g., 0.6)")

async def switch_on_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, pair=None, value=True):
	if pair is None:
		await get_pair(update, context, "switch_on")
		return
	await set_trade_mode(update, value, pair)

async def switch_off_handle(update: Update, context: ContextTypes.DEFAULT_TYPE, pair=None, value=False):
	if pair is None:
		await get_pair(update, context, "switch_off")
		return
	await set_trade_mode(update, value, pair)

async def set_trade_mode(update, value, pair):
	mod = "ON" if value else "OFF"
	try:
		pair.my_wallet.set_mode(value)
		message = f"{pair.name} wallet trade mode is {mod}"
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text(message)
	except ValueError:
		msg = update.callback_query.message if update.callback_query else update.message
		await msg.reply_text(f"Failed to switch {mod} {pair.name} walllet trade mode")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	data = query.data

	command_map = {
		"help": help_handle,
		"get_my_balance": get_my_balance_handle,
		"get_my_positions": get_my_positions_handle,
		"get_target_positions": get_target_positions_handle,
		"set_target_address": set_target_address_handle,
		"switch_on": switch_on_handle,
		"switch_off": switch_off_handle,
	}
	if "command" in context.user_data:
		command = context.user_data.pop('command')
		handler_func = command_map.get(command)
		if handler_func:
			await handler_func(update, context, pair=pairs_data[data])
	elif data in command_map:
		await command_map[data](update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if 'awaiting' in context.user_data:
		command = context.user_data.pop('awaiting')
		command_map = {
			"set_target_address": set_target_address_handle,
		}
		if command in command_map:
			await command_map[command](update, context, context.user_data['pair'], value=update.message.text)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and auto-restart polling on network issues"""
    error = context.error
    
    if isinstance(error, (NetworkError, TimedOut)):
        print(f"Network error (will auto-recover): {error}")
        # Wait a bit then let PTB retry automatically
        await asyncio.sleep(5)
        return
    
    # For all other errors
    print(f"Unhandled error: {error}")
    if update:
        try:
            await update.effective_message.reply_text("Bot error — restarting...")
        except:
            pass

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
	application.add_error_handler(error_handler)
	
async def keep_alive_silent():
	while True:
		await asyncio.sleep(600)  # 15 minutes
		try:
			await application.bot.get_me()  # Silent API call to keep connection alive
		except Exception as e:
			print(f"Silent keep-alive error: {e}")

async def start_bot():
	global application, bot_event_loop
	application = Application.builder().token(TELEGRAM_TOKEN).build()
	add_all_handlers()
	
	print("Starting Telegram bot polling...")
	await application.initialize()
	await application.start()
	await post_init()
	
	while True:
		# Start Telegram Bot
		try:
			await application.updater.start_polling(
				timeout=30,
				drop_pending_updates=True,
				poll_interval=1.0,
				bootstrap_retries=-1,
			)
			# Save the real running loop
			bot_event_loop = asyncio.get_running_loop()

			# Keep the async function alive forever
			await asyncio.Event().wait()
			# Start keep-alive task
			asyncio.create_task(keep_alive_silent())
			print("application started")
			break  # Exit retry loop if polling starts successfully
		except Exception as e:
			message = f"Polling error: {e}. Retrying in 5 seconds..."
			send_telegram_message(message)
			print(message)
			await asyncio.sleep(5)


def start_telegram_bot_thread(pairs: dict):
	global pairs_data
	pairs_data = pairs

	def start_thread_bot():
		asyncio.run(start_bot())
	thread = threading.Thread(target=start_thread_bot, daemon=True)
	thread.start()
	print("Telegram bot thread launched")
	return thread

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