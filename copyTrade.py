import os
import time
import asyncio
import threading
from bot import send_telegram_message, start_bot
from wallet import my_wallet, target_wallet
from typing import Dict, Any, List
from notion import log_to_database
from dotenv import load_dotenv
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from eth_account import Account
from eth_account.signers.local import LocalAccount

load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLL_INTERVAL = 2
IS_CROSS = True

async def copy_trade():
	last_timestamp = int(time.time()*1000)
	account: LocalAccount = Account.from_key(PRIVATE_KEY)
	exchange = Exchange(account, constants.MAINNET_API_URL)
	
	# start telegram bot
	await start_bot()

	while True:
		try:
			# Fetch new fills since last_timestamp
			new_fills: List[Dict] = target_wallet.get_filled_history(last_timestamp)
			if not new_fills:
				# time.sleep(POLL_INTERVAL)
				await asyncio.sleep(POLL_INTERVAL)
				continue
			target_wallet.update_user_state()
			# target_wallet.update_positions()
			
			for fill in new_fills:
				if 'Close' in fill['dir'] and fill['coin'] not in my_wallet.positions.keys():
					await send_telegram_message(f"Target wallet {fill['dir']} {fill['coin']} position")
					last_timestamp = max(f['time'] for f in new_fills)
					continue
				percentage_asset, leverage_value, entry_price = target_wallet.get_position_info(fill['coin'])

				user_margin = percentage_asset * my_wallet.asset
				user_order_sz = round((user_margin * leverage_value) / entry_price, 5)
				is_buy = True if fill['side'] == 'B' else False
				print("calculation completed")
				exchange.update_leverage(leverage_value, fill['coin'], is_cross=IS_CROSS)
				print("updated leverage")
				if my_wallet.mode:
					order_result = exchange.market_open(fill['coin'], is_buy, user_order_sz, None, 0.01)
				else:
					order_result = exchange.market_open(fill['coin'], is_buy, 0, None, 0.01)
				print("sent order")
				message = ""
				if order_result['status'] == 'ok':
					message += f"Market Order: {fill['coin']}\n"
					position = 'Long' if is_buy else 'Short'
					message += f"Position: {position}\n"
					message += f"Leverage: {leverage_value}X\n"
					message += f"Size: {user_order_sz}\n"
					message += f"Price: {entry_price}"
					message += str(order_result['response'])
				else:
					message += f"Market order failed with {fill['coin']}, size {user_order_sz}, position {position}"
				await send_telegram_message(message)
				print(message)

			# Log to Notion
			my_wallet.update_user_state()
			my_fills = my_wallet.get_filled_history(last_timestamp)
			for fill in my_fills:
				coin = fill['coin']
				dir = 'Long' if fill['side'] == 'B' else 'Short'
				price = fill['px']
				pnl = float(fill['closedPnl'])
				fee = float(fill['fee'])
				log_to_database(coin, dir, price, pnl, fee)


			# new_orders: List[Dict] = target_wallet.get_historical_orders(last_timestamp)
			# for order in new_orders:
			# 	if order['coin'] not in my_wallet.positions.keys():
			# 		continue
			# 	is_buy = True if order['side'] == 'B' else False
			# 	order_type = {'trigger': {'isMarket': False, 'triggerPx':order['triggerPx'], 'tpsl': 'sl' if order['orderType'] == 'Stop Limit' else 'tp'}}
			# 	order_result = exchange.order(order['coin'], is_buy, my_wallet.positions[order['coin']], order['limitPx'], order_type, order['reduceOnly'])
			# 	print("order sent")
			# 	message = ""
			# 	if order_result['status'] == 'ok':
			# 		message += f"Order: {fill['coin']}"
			# 		position = 'Long' if is_buy else 'Short'
			# 		message += f"Position: {position}"
			# 		message += f"Leverage: {leverage_value}X\n"
			# 		message += f"Size: {user_order_sz}"
			# 		message += str(order_result['response'])
			# 	else:
			# 		message += f"Order failed with {fill['coin']}, size {user_order_sz}, position {position}"
			# 	await send_telegram_message(message)
			# 	print(message)

			# Update last_timestamp
			last_timestamp = max(f['time'] for f in new_fills)

		except Exception as e:
			print(f"Error in poll: {e}")
			last_timestamp = max(f['time'] for f in new_fills)
		
		await asyncio.sleep(POLL_INTERVAL)
		# time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
	try:
		asyncio.run(copy_trade())
	except KeyboardInterrupt:
		print(f"Shutting down...")