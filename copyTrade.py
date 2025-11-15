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

async def send_message(order_result, coin, direction, size, price, leverage_value=0):
	if order_result['status'] == 'ok':
		message += f"Market Order: {coin}\n"
		# position = 'Long' if is_buy else 'Short'
		message += f"Direction: {direction}\n"
		if leverage_value != 0:
			message += f"Leverage: {leverage_value}X\n"
		message += f"Size: {size}\n"
		message += f"Price: {price}\n"
		message += str(order_result['response'])
	else:
		message += f"Market order failed to {direction} {coin} position with size {size} on price {price}"
	await send_telegram_message(message)
	print(message)

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

			print(f"timestamp: {last_timestamp}")
			print(f"new_fills: \n {new_fills}")
			# await send_telegram_message("found new fill")
			target_wallet.update_user_state()
			# target_wallet.update_positions()
			
			for fill in new_fills:
				print(f"fill: \n {fill}")
				if "@" in fill['coin']:
					print("Spot trading detected")					
					continue
				
				message = ""
				if 'Close' in fill['dir'] and fill['coin'] not in my_wallet.positions.keys():
					message += f"Target wallet {fill['dir']} {fill['coin']} position"
					await send_telegram_message(message)
					print(message)
					last_timestamp = fill['time'] + 1
					continue
				
				elif 'Close' in fill['dir'] and fill['coin'] in my_wallet.positions.keys():
					my_wallet.update_positions()
					user_size = my_wallet.positions[fill['coin']]
					is_buy = True if user_size < 0 else False
					order_result = exchange.market_open(fill['coin'], is_buy, user_size, None, 0.01)
					send_message(order_result, fill['coin'], fill['dir'], user_size, fill['px'])

				else:
					_, leverage_value, _ = target_wallet.get_position_info(fill['coin'])
					percentage_size = float(fill['sz']) / target_wallet.asset
					user_size = round(percentage_size * float(my_wallet.asset), 5)
					is_buy = True if fill['side'] == 'B' else False
					print(f"Target wallet used {percentage_size*100}% of asset")
					exchange.update_leverage(leverage_value, fill['coin'], is_cross=IS_CROSS)
					print(f"{leverage_value}X leverage set")

					if my_wallet.mode:
						order_result = exchange.market_open(fill['coin'], is_buy, user_size, None, 0.01)
					else:
						order_result = exchange.market_open(fill['coin'], is_buy, 0, None, 0.01)
					print("Market order sent")				
					
					send_message(order_result, fill['coin'], fill['dir'], user_size, fill['px'], leverage_value)

			# Log to Notion
			my_wallet.update_user_state()
			my_fills = my_wallet.get_filled_history(last_timestamp)
			for fill in my_fills:
				coin = fill['coin']
				dir = 'Long' if fill['side'] == 'B' else 'Short'
				price = float(fill['px'])
				size = float(fill['sz'])
				pnl = float(fill['closedPnl'])
				if "Open" not in fill['dir']:
					_, leverage_value, _ = my_wallet.get_position_info(fill['coin'])
					# percentage_pnl = (fill['px'] - entry_price) / entry_price * leverage_value if fill['side'] == 'B' else (entry_price - fill['px']) / entry_price * leverage_value
					# fee calculation excluded
					percentage_pnl =  pnl / (my_wallet.asset - pnl) * 100 * leverage_value
				else:
					percentage_pnl = 0
				fee = float(fill['fee'])
				timestamp = int(fill['time'])
				await log_to_database(coin, dir, price, size, pnl, percentage_pnl, fee, timestamp)

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
			# 		message += f"Size: {user_size}"
			# 		message += str(order_result['response'])
			# 	else:
			# 		message += f"Order failed with {fill['coin']}, size {user_size}, position {position}"
			# 	await send_telegram_message(message)
			# 	print(message)

			# Update last_timestamp
			last_timestamp = max(f['time'] for f in new_fills) + 1

		except Exception as e:
			print(f"Error in poll: {e}")
			await send_telegram_message("Error found. Terminating the program")
			break
		
		await asyncio.sleep(POLL_INTERVAL)
		# time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
	try:
		asyncio.run(copy_trade())
	except KeyboardInterrupt:
		print(f"Shutting down...")