import time
from typing import Dict
from hyperliquid.info import Info
from hyperliquid.utils import constants

info = Info(constants.MAINNET_API_URL, skip_ws=False)

class Wallet:
	def __init__(self, address):
		self.address = address
		self.positions: Dict[str, float] = {}

		self.update_user_state()
		self.update_positions()

	def update_user_state(self):
		self.user_state = info.user_state(self.address)
		self.asset = self.user_state['marginSummary']['accountValue']
		self.asset_positions = self.user_state['assetPositions']

	def update_positions(self):
		self.positions.clear()
		for pos in self.user_state.get('assetPositions', []):
			coin = pos['position']['coin']
			szi = float(pos['position']['szi'])
			if abs(szi) > 0:
				self.positions[coin] = szi
		
	def get_filled_history(self, start_time):
		return info.user_fills_by_time(self.address, start_time, int(time.time()*1000), True) #sorted(info.user_fills_by_time(self.address, start_time, int(time.time()*1000), True), key=lambda x: x['time'])
	
	def get_historical_orders(self, start_time):
		return [data['order'] for data in info.historical_orders(self.address) if data['order']['timestamp'] > start_time]

	def get_position_info(self, coin):
		position_info = [data['position'] for data in self.asset_positions if data['position']['coin'] == coin]
		percentage_asset = int(position_info[0]['marginUsed'] / self.asset)
		leverage_value = position_info[0]['leverage']['value']
		entry_price = position_info[0]['entryPx']
		return percentage_asset, leverage_value, entry_price
	
