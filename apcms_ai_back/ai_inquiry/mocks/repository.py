import json
from pathlib import Path
DATA=Path(__file__).with_name('dummy_data.json')
class MockRepository:
 def __init__(self): self.data=json.loads(DATA.read_text(encoding='utf-8'))
 def authenticate(self,user_id):
  if user_id is None: return None
  return next((u for u in self.data['users'] if u['user_id']==str(user_id)),None)
 def get(self,user_id,category):
  table={'RESERVATION':'reservations','USAGE':'parking_usage','VEHICLE':'vehicles','MILEAGE':'mileage','FEE':'maintenance_fees'}[category]
  return [{k:v for k,v in row.items() if k!='user_id'} for row in self.data[table] if row['user_id']==str(user_id)]
