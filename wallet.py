import time
import os
import threading
from typing import Dict
from hyperliquid.info import Info
from hyperliquid.utils import constants
from dotenv import load_dotenv

load_dotenv()
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
TARGET_ADDRESS = os.getenv("TARGET_ADDRESS")

info = Info(constants.MAINNET_API_URL, skip_ws=False)

class Wallet:
	def __init__(self, address):
		self.address = address
		self.positions: Dict[str, float] = {}
		self._lock = threading.Lock()
		self.mode = True

		self.update_user_state()
		self.update_positions()

	def set_address(self, address):
		with self._lock:
			self.address = address
		self.update_user_state()
		self.update_positions()

	def set_mode(self, mode):
		with self._lock:
			self.mode = mode

	def update_user_state(self):
		with self._lock:
			self.user_state = info.user_state(self.address)
			self.asset = float(self.user_state['marginSummary']['accountValue'])
			self.asset_positions = self.user_state['assetPositions']

	def update_positions(self):
		with self._lock:
			self.positions.clear()
			for pos in self.user_state.get('assetPositions', []):
				coin = pos['position']['coin']
				szi = float(pos['position']['szi'])
				if szi > 0:
					self.positions[coin] = szi
		
	def get_filled_history(self, start_time):
		with self._lock:
			return info.user_fills_by_time(self.address, start_time, int(time.time()*1000), True) #sorted(info.user_fills_by_time(self.address, start_time, int(time.time()*1000), True), key=lambda x: x['time'])
	
	def get_historical_orders(self, start_time):
		with self._lock:
			return [data['order'] for data in info.historical_orders(self.address) if data['order']['timestamp'] > start_time]

	def get_position_info(self, coin):
		with self._lock:
			position_info = [data['position'] for data in self.asset_positions if data['position']['coin'] == coin]
			percentage_asset = float(position_info[0]['marginUsed']) / self.asset
			leverage_value = int(position_info[0]['leverage']['value'])
			entry_price = float(position_info[0]['entryPx'])
			return percentage_asset, leverage_value, entry_price
	
global target_wallet, my_wallet
target_wallet = Wallet(TARGET_ADDRESS)
my_wallet = Wallet(WALLET_ADDRESS)
print(my_wallet.address)