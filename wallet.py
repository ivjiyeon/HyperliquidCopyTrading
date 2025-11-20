import time
import os
import threading
import yaml
from typing import Dict, List
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from eth_account import Account
from eth_account.signers.local import LocalAccount
from dotenv import load_dotenv

load_dotenv()
# WALLET_ADDRESS_L = os.getenv("WALLET_ADDRESS_L")
# TARGET_ADDRESS = os.getenv("TARGET_ADDRESS")
# PRIVATE_KEY_L = os.getenv("PRIVATE_KEY_L")
IS_CROSS=True

info = Info(constants.MAINNET_API_URL, skip_ws=False)

class Wallet:
	def __init__(self, address):
		self.address = address
		self.positions: Dict[str, float] = {}
		self._lock = threading.Lock()

		self.update_user_state()

	def set_address(self, address):
		with self._lock:
			self.address = address
		self.update_user_state()

	def update_user_state(self):
		with self._lock:
			self.user_state = info.user_state(self.address)
			self.asset = float(self.user_state['marginSummary']['accountValue'])
			self.asset_positions = self.user_state['assetPositions']
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
	
	
class My_Wallet(Wallet):
	def __init__(self, address, private_key):
		super().__init__(address)
		account: LocalAccount = Account.from_key(private_key)
		self.exchange = Exchange(account, constants.MAINNET_API_URL)
		self.mode = False
	
	def update_leverage(self, coin, leverage_value):
		self.exchange.update_leverage(leverage_value, coin, is_cross=IS_CROSS)
		print(f"{leverage_value}X leverage set")

	def send_market_order(self, coin, dir, size):
		if self.mode:
			order_result = self.exchange.market_open(coin, dir, size, None, 0.01)
		else:
			order_result = self.exchange.market_open(coin, dir, 0, None, 0.01)
		print("Market order sent")
		return order_result
	
	def set_mode(self, mode):
		with self._lock:
			self.mode = mode
		
def load_config() -> Dict[str, Any]:
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("config.yaml not found! Create it using the example above.")
        exit(1)
    except Exception as e:
        print(f"Error reading config.yaml: {e}")
        exit(1)


config = load_config()
pairs = config.get("pairs")

copy_pairs: Dict[List] = {}
for pair in pairs:
	private_key = os.getenv(pair['private_key'])
	copy_pairs[pair['name']]= [
		My_Wallet(pair['my_wallet'], private_key), 
		Wallet(pair['target_wallet'])
	]

# # global target_wallet, my_wallet
# target_wallet = Wallet(TARGET_ADDRESS)
# my_wallet = My_Wallet(WALLET_ADDRESS_L, PRIVATE_KEY_L)

# COPY_PAIRS=[
# 	(my_wallet, target_wallet, "LONG")
# ]

# print(my_wallet.address)