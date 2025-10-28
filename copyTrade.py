import os
import time
from wallet import Wallet
from typing import Dict, Any, List
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants


WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
TARGET_ADDRESS = os.getenv("TARGET_ADDRESS")
POLL_INTERVAL = 2
IS_CROSS = True

if __name__ == '__main__':
	target_wallet = Wallet(TARGET_ADDRESS)
	my_wallet = Wallet(WALLET_ADDRESS)
	last_timestamp = int(time.time()*1000)
	exchange = Exchange(constants.MAINNET_API_URL, account_address=WALLET_ADDRESS) 


	while True:
		try:
			# Fetch new fills since last_timestamp
			new_fills: List[Dict] = target_wallet.get_filled_history(last_timestamp)
			if not new_fills:
				time.sleep(POLL_INTERVAL)
				continue

			target_wallet.update_user_state()
			# target_wallet.update_positions()
			
			for fill in new_fills:
				if 'Close' in fill['dir'] and fill['coin'] not in my_wallet.positions.keys():
					continue
				percentage_asset, leverage_value, entry_price = target_wallet.get_position_info(fill['coin'])

				user_margin = percentage_asset * my_wallet.asset
				user_order_sz = (user_margin * leverage_value) / entry_price
				is_buy = True if fill['side'] == 'B' else False

				exchange.update_leverage(leverage_value, fill['coin'], is_cross=IS_CROSS)
				order_result = exchange.market_open(fill['coin'], is_buy, user_order_sz, None, 0.01)

			my_wallet.update_user_state()

			new_orders: List[Dict] = target_wallet.get_historical_orders(last_timestamp)
			for order in new_orders:
				is_buy = True if order['side'] == 'B' else False
				order_type = {'trigger': {'isMarket': False, 'triggerPx':order['triggerPx'], 'tpsl': 'sl' if order['orderType'] == 'Stop Limit' else 'tp'}}
				exchange.order(order['coin'], is_buy, my_wallet.positions[order['coin']], order['limitPx'], order_type, order['reduceOnly'])

			# Update last_timestamp
			last_timestamp = max(f['time'] for f in new_fills)

		except Exception as e:
			print(f"Error in poll: {e}")
		
		time.sleep(POLL_INTERVAL)