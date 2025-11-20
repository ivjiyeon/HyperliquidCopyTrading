import os
import time
import asyncio
import threading
from bot import send_telegram_message, start_telegram_bot_thread
from utils import load_config
from wallet import My_Wallet, Wallet
from typing import Dict, Any, List
from notion import log_to_database
from hyperliquid.info import Info
from hyperliquid.utils import constants
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL = 2

class CopyTradingPair():
	def __init__(self, name, my_wallet: My_Wallet, target_wallet: Wallet):
		self.my_wallet = my_wallet
		self.target_wallet = target_wallet
		self.running = True
		self.name = name
		
		notion = config.get("notion")
		for database in notion:
			if database['name'] == self.name:
				self.db_id = os.getenv(database['db_id'])
	
	def start_thread_run(self):
		asyncio.run(self.worker())

	def start(self):		
		thread = threading.Thread(target=self.start_thread_run, daemon=True)
		thread.start()
		return thread

	def stop(self):
		self.running = False
			
	async def worker(self):
		print(f"[{self.name}] Copy thread STARTED")
		
		last_timestamp = int(time.time()*1000)
		my_timestamp = int(time.time()*1000)
		info = Info(constants.MAINNET_API_URL, skip_ws=False)
		
		meta = info.meta()		
		# create a szDecimals map
		sz_decimals = {}
		for asset_info in meta["universe"]:
			sz_decimals[asset_info["name"]] = asset_info["szDecimals"]
		# max_decimals = 6  # change to 8 for spot
		


		while self.running:
			try:
				# Fetch new fills since last_timestamp
				new_fills: List[Dict] = self.target_wallet.get_filled_history(last_timestamp)
				if not new_fills:
					# time.sleep(POLL_INTERVAL)
					await asyncio.sleep(POLL_INTERVAL)
					continue

				print(f"timestamp: {last_timestamp}")
				print(f"new_fills: \n {new_fills}")
				# await send_telegram_message("found new fill")
				self.target_wallet.update_user_state()
				self.my_wallet.update_user_state()
				
				for fill in new_fills:
					print(f"fill: \n {fill}")
					if "@" in fill['coin']:
						print("Spot trading detected")					
						continue
									
					if 'Close' in fill['dir'] and fill['coin'] not in self.my_wallet.positions.keys():
						message = f"--------{self.name} Wallet Order Information--------\nTarget wallet {fill['dir']} {fill['coin']} position"
						await send_telegram_message(message)
						print(message)
						last_timestamp = fill['time'] + 1
						continue
					
					elif 'Close' in fill['dir'] and fill['coin'] in self.my_wallet.positions.keys():
						if self.target_wallet.positions[fill['coin']] > 0:
							target_pct = float(fill['sz']) / (float(fill['sz']) + self.target_wallet.positions[fill['coin']])
							user_size = round(target_pct * self.my_wallet.positions[fill['coin']], sz_decimals[fill['coin']])
						else:
							user_size = self.my_wallet.positions[fill['coin']]
						is_buy = True if user_size < 0 else False
						order_result = self.my_wallet.send_market_order(fill['coin'], is_buy, user_size)
						await self.send_message(order_result, fill['coin'], fill['dir'], user_size, fill['px'])

					else:
						_, leverage_value, _ = self.target_wallet.get_position_info(fill['coin'])
						percentage_size = float(fill['sz']) / self.target_wallet.asset
						user_size = round(percentage_size * float(self.my_wallet.asset), sz_decimals[fill['coin']])
						is_buy = True if fill['side'] == 'B' else False
						print(f"Target wallet used {percentage_size*100*float(fill['px'])}% of asset")
						self.my_wallet.update_leverage(fill['coin'], leverage_value)
						order_result = self.my_wallet.send_market_order(fill['coin'], is_buy, user_size)				
						
						await self.send_message(order_result, fill['coin'], fill['dir'], user_size, fill['px'], leverage_value)

				# Update last_timestamp
				last_timestamp = max(f['time'] for f in new_fills) + 1

				# Log to Notion
				self.my_wallet.update_user_state()
				my_fills = self.my_wallet.get_filled_history(my_timestamp)
				print(f"my fills: \n{my_fills}")
				if my_fills == None:
					print("WHY")
					continue
				for fill in my_fills:
					print(f"fill: \n{fill}")
					coin = fill['coin']
					dir = 'Long' if fill['side'] == 'B' else 'Short'
					price = float(fill['px'])
					size = float(fill['sz'])
					pnl = float(fill['closedPnl'])
					if "Open" not in fill['dir']:
						_, leverage_value, _ = self.my_wallet.get_position_info(fill['coin'])
						# percentage_pnl = (fill['px'] - entry_price) / entry_price * leverage_value if fill['side'] == 'B' else (entry_price - fill['px']) / entry_price * leverage_value
						# fee calculation excluded
						percentage_pnl =  pnl / (self.my_wallet.asset - pnl) * 100 * leverage_value
					else:
						percentage_pnl = 0
					fee = float(fill['fee'])
					timestamp = int(fill['time'])
					await log_to_database(self.db_id, coin, dir, price, size, pnl, percentage_pnl, fee, timestamp)
					print(f"logged to notion at {timestamp}")

				# Update last_timestamp
				my_timestamp = max(f['time'] for f in my_fills) + 1

			except Exception as e:
				print(f"Error in poll: {e}")
				await send_telegram_message("Error found. Terminating the program")
				break
		print(f"[{self.name}] Copy thread STOPPED")
		
	async def send_message(self, order_result, coin, direction, size, price, leverage_value=0):
		message = f"--------{self.name} Wallet Order Information--------\n"
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
	global config
	config = load_config()
	pairs = config.get("pairs")
	copy_pairs: Dict[CopyTradingPair] = {}
	for pair in pairs:
		private_key = os.getenv(pair['private_key'])
		pair = CopyTradingPair(
			pair['name'], 
			My_Wallet(pair['my_wallet'], private_key), 
			Wallet(pair['target_wallet'])
		)
		copy_pairs[pair.name] = pair

	# start telegram bot
	# await start_bot()
	start_telegram_bot_thread(copy_pairs)
	
	threads=[]
	for pair in copy_pairs.values():
		thread = pair.start()
		threads.append(thread)
	print("copy pairs created")
		
	for thread in threads:
		thread.join()
		
	# info = Info(constants.MAINNET_API_URL, skip_ws=False)
	# meta = info.meta()
	# # create a szDecimals map
	# sz_decimals = {}
	# for asset_info in meta["universe"]:
	# 	sz_decimals[asset_info["name"]] = asset_info["szDecimals"]
	# # max_decimals = 6  # change to 8 for spot

	# while True:
	# 	try:
	# 		# Fetch new fills since last_timestamp
	# 		new_fills: List[Dict] = target_wallet.get_filled_history(last_timestamp)
	# 		if not new_fills:
	# 			# time.sleep(POLL_INTERVAL)
	# 			await asyncio.sleep(POLL_INTERVAL)
	# 			continue

	# 		print(f"timestamp: {last_timestamp}")
	# 		print(f"new_fills: \n {new_fills}")
	# 		# await send_telegram_message("found new fill")
	# 		target_wallet.update_user_state()
	# 		my_wallet.update_user_state()
			
	# 		for fill in new_fills:
	# 			print(f"fill: \n {fill}")
	# 			if "@" in fill['coin']:
	# 				print("Spot trading detected")					
	# 				continue
								
	# 			if 'Close' in fill['dir'] and fill['coin'] not in my_wallet.positions.keys():
	# 				message = f"Target wallet {fill['dir']} {fill['coin']} position"
	# 				await send_telegram_message(message)
	# 				print(message)
	# 				last_timestamp = fill['time'] + 1
	# 				continue
				
	# 			elif 'Close' in fill['dir'] and fill['coin'] in my_wallet.positions.keys():
	# 				user_size = my_wallet.positions[fill['coin']]
	# 				is_buy = True if user_size < 0 else False
	# 				order_result = my_wallet.send_market_order(fill['coin'], is_buy, user_size)
	# 				# order_result = exchange.market_open(fill['coin'], is_buy, user_size, None, 0.01)
	# 				await send_message(order_result, fill['coin'], fill['dir'], user_size, fill['px'])

	# 			else:
	# 				_, leverage_value, _ = target_wallet.get_position_info(fill['coin'])
	# 				percentage_size = float(fill['sz']) / target_wallet.asset
	# 				user_size = round(percentage_size * float(my_wallet.asset), sz_decimals[fill['coin']])
	# 				is_buy = True if fill['side'] == 'B' else False
	# 				print(f"Target wallet used {percentage_size*100*float(fill['px'])}% of asset")
	# 				my_wallet.update_leverage(fill['coin'], leverage_value)
	# 				order_result = my_wallet.send_market_order(fill['coin'], is_buy, user_size)				
					
	# 				await send_message(order_result, fill['coin'], fill['dir'], user_size, fill['px'], leverage_value)

	# 		# Update last_timestamp
	# 		last_timestamp = max(f['time'] for f in new_fills) + 1

	# 		# Log to Notion
	# 		my_wallet.update_user_state()
	# 		my_fills = my_wallet.get_filled_history(my_timestamp)
	# 		print(f"my fills: \n{my_fills}")
	# 		for fill in my_fills:
	# 			print(f"fill: \n{fill}")
	# 			coin = fill['coin']
	# 			dir = 'Long' if fill['side'] == 'B' else 'Short'
	# 			price = float(fill['px'])
	# 			size = float(fill['sz'])
	# 			pnl = float(fill['closedPnl'])
	# 			if "Open" not in fill['dir']:
	# 				_, leverage_value, _ = my_wallet.get_position_info(fill['coin'])
	# 				# percentage_pnl = (fill['px'] - entry_price) / entry_price * leverage_value if fill['side'] == 'B' else (entry_price - fill['px']) / entry_price * leverage_value
	# 				# fee calculation excluded
	# 				percentage_pnl =  pnl / (my_wallet.asset - pnl) * 100 * leverage_value
	# 			else:
	# 				percentage_pnl = 0
	# 			fee = float(fill['fee'])
	# 			timestamp = int(fill['time'])
	# 			await log_to_database(coin, dir, price, size, pnl, percentage_pnl, fee, timestamp)
	# 			print(f"logged to notion at {timestamp}")

	# 		# Update last_timestamp
	# 		my_timestamp = max(f['time'] for f in my_fills) + 1

	# 		# new_orders: List[Dict] = target_wallet.get_historical_orders(last_timestamp)
	# 		# for order in new_orders:
	# 		# 	if order['coin'] not in my_wallet.positions.keys():
	# 		# 		continue
	# 		# 	is_buy = True if order['side'] == 'B' else False
	# 		# 	order_type = {'trigger': {'isMarket': False, 'triggerPx':order['triggerPx'], 'tpsl': 'sl' if order['orderType'] == 'Stop Limit' else 'tp'}}
	# 		# 	order_result = exchange.order(order['coin'], is_buy, my_wallet.positions[order['coin']], order['limitPx'], order_type, order['reduceOnly'])
	# 		# 	print("order sent")
	# 		# 	message = ""
	# 		# 	if order_result['status'] == 'ok':
	# 		# 		message += f"Order: {fill['coin']}"
	# 		# 		position = 'Long' if is_buy else 'Short'
	# 		# 		message += f"Position: {position}"
	# 		# 		message += f"Leverage: {leverage_value}X\n"
	# 		# 		message += f"Size: {user_size}"
	# 		# 		message += str(order_result['response'])
	# 		# 	else:
	# 		# 		message += f"Order failed with {fill['coin']}, size {user_size}, position {position}"
	# 		# 	await send_telegram_message(message)
	# 		# 	print(message)


	# 	except Exception as e:
	# 		print(f"Error in poll: {e}")
	# 		await send_telegram_message("Error found. Terminating the program")
	# 		break
		
	# 	await asyncio.sleep(POLL_INTERVAL)
	# 	# time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
	try:
		asyncio.run(copy_trade())
	except KeyboardInterrupt:
		print(f"Shutting down...")