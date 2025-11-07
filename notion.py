import os
import datetime
from notion_client import AsyncClient


notion = AsyncClient(auth=os.getenv("NOTION_TOKEN"))
database_id = os.getenv("DATABASE_ID")

async def log_to_database(coin, dir, price, pnl, fee):
	# new_page = 
	await notion.pages.create(
		parent={"database_id": database_id},
		properties={
			"Date": {  # Date property
				"date": {
					"start": datetime.date.today().isoformat() #"2025-11-10"
				}
			},
			"Coin": {  # Rich text
				"rich_text": [
					{
						"text": {
							"content": coin
						}
					}
				]
			},
			"Direction": {  # Select
				"select":{
					"name": dir
				}				
			},
			"Price": {
				"number": price
			},
			"ClosedPNL": {  # Number
				"number": pnl
			},
			"Fee": {  # Number
				"number": fee
			}
		}
	)
	# print("added to database")
	# print(new_page)
	