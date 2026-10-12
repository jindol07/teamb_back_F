from ai_inquiry.router import classify
from ai_inquiry.mocks.repository import MockRepository
from ai_inquiry.mocks.conversation_db import insert_exchange,connect

def test_routes():
 assert classify('내 예약 어디야?')['categories']==['RESERVATION']
 assert classify('내 주차 이용 기록 알려줘')['categories']==['USAGE']
 assert classify('차량을 추가하려면 어떻게 해?')['type']=='POLICY'
 assert classify('내 예약 위치와 예약 방법 알려줘')['type']=='MIXED'

def test_office_isolation():
 repo=MockRepository()
 assert repo.get('1','RESERVATION')[0]['reservation_id']==100
 assert repo.get('2','RESERVATION')[0]['reservation_id']==101
 assert repo.get('1','USAGE')[0]['usage_id']==700
 assert repo.get('2','USAGE')[0]['usage_id']==701

def test_inserts(monkeypatch,tmp_path):
 from ai_inquiry.config import settings
 config=settings().copy(); config['mock_db']=tmp_path/'test.sqlite3'
 monkeypatch.setattr('ai_inquiry.mocks.conversation_db.settings',lambda: config)
 insert_exchange('1','conv-test','문의 내용','답변 내용')
 with connect() as c:
  assert c.execute('SELECT COUNT(*) FROM INQUIRY_CONVERSATION').fetchone()[0]==1
  assert c.execute('SELECT COUNT(*) FROM INQUIRY_MESSAGE').fetchone()[0]==2
 try:
  insert_exchange('2','conv-test','다른 사용자','금지')
  raise AssertionError('cross-user access accepted')
 except PermissionError: pass
