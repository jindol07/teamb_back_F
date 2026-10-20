from ai_inquiry.router import classify
import asyncio
import pytest
from ai_inquiry.mocks.repository import MockRepository
from ai_inquiry.mocks.conversation_db import insert_exchange,connect

def test_routes():
 assert classify('내 예약 어디야?')['categories']==['RESERVATION']
 assert classify('내 주차 이용 기록 알려줘')['categories']==['USAGE']
 assert classify('차량을 추가하려면 어떻게 해?')['type']=='POLICY'
 assert classify('내 예약 위치와 예약 방법 알려줘')['type']=='MIXED'


@pytest.mark.parametrize('question,categories,kind', [
 ('내 최근 주차이력 알려줘', ['USAGE'], 'USAGE'),
 ('주차 이력 보여줘', ['USAGE'], 'USAGE'),
 ('내 주차 이용 내역 알려줘', ['USAGE'], 'USAGE'),
 ('어제 언제 입차했어?', ['USAGE'], 'USAGE'),
 ('마지막 출차 시간이 언제야?', ['USAGE'], 'USAGE'),
 ('이번 달 주차 이용 기록 알려줘', ['USAGE'], 'USAGE'),
 ('내 예약 어디야?', ['RESERVATION'], 'RESERVATION'),
 ('내일 예약된 주차면 알려줘', ['RESERVATION'], 'RESERVATION'),
 ('예약 시작 시간이 언제야?', ['RESERVATION'], 'RESERVATION'),
 ('취소한 예약 내역 보여줘', ['RESERVATION'], 'RESERVATION'),
 ('내 차량 번호 알려줘', ['VEHICLE'], 'VEHICLE'),
 ('차량 승인됐어?', ['VEHICLE'], 'VEHICLE'),
 ('내 차량 등록이 왜 반려됐어?', ['VEHICLE'], 'VEHICLE'),
 ('지금 빈 자리 있어?', ['PARKING_STATUS'], 'PARKING_STATUS'),
 ('주차 가능한 곳 알려줘', ['PARKING_STATUS'], 'PARKING_STATUS'),
 ('남은 주차면 몇 개야?', ['PARKING_STATUS'], 'PARKING_STATUS'),
 ('현재 주차장 혼잡해?', ['PARKING_STATUS'], 'PARKING_STATUS'),
 ('내일 예약 어떻게 해?', [], 'POLICY'),
 ('내 예약 취소 방법 알려줘', [], 'POLICY'),
 ('예약 확인 방법 알려줘', [], 'POLICY'),
 ('차량 등록 절차 알려줘', [], 'POLICY'),
 ('주차요금 기준 알려줘', [], 'POLICY'),
 ('내 예약 위치와 취소 방법 알려줘', ['RESERVATION'], 'MIXED'),
 ('내 예약과 취소 방법 알려줘', ['RESERVATION'], 'MIXED'),
 ('내 예약이랑 등록 차량 알려줘', ['RESERVATION', 'VEHICLE'], 'MULTI_DB'),
 ('내 예약과 빈자리 알려줘', ['RESERVATION', 'PARKING_STATUS'], 'MULTI_DB'),
 ('내 예약 취소해줘', [], 'ACTION'),
 ('차량 등록해 주세요', [], 'ACTION'),
 ('내 차 어디 있어?', [], 'CLARIFY'),
 ('내 차량 위치 알려줘', [], 'CLARIFY'),
 ('내 보유 포인트 알려줘', ['MILEAGE'], 'MILEAGE'),
 ('이번 달 관리비 내역 알려줘', ['FEE'], 'FEE'),
 ('안녕', [], 'UNKNOWN'),
])
def test_question_classification(question, categories, kind):
 result = classify(question)
 assert result['categories'] == categories
 assert result['type'] == kind


@pytest.mark.parametrize('question,kind', [
 ('내 예약 취소해줘', 'ACTION'),
 ('내 차 어디 있어?', 'CLARIFY'),
])
def test_guidance_does_not_query_data_or_llm(monkeypatch, question, kind):
 from ai_inquiry import service
 config = {'mode': 'MOCK', 'test_reservation_enabled': False}
 monkeypatch.setattr(service, 'settings', lambda: config)
 def unexpected(*args, **kwargs):
  pytest.fail('안내/되묻기는 데이터 조회와 LLM 호출이 없어야 합니다.')
 monkeypatch.setattr(service.MockRepository, 'get', unexpected)
 monkeypatch.setattr(service, 'generate_answer', unexpected)
 saved_payloads = []
 monkeypatch.setattr(service, 'insert_exchange', lambda *args: saved_payloads.append(args) or {'saved': True})
 result = asyncio.run(service.answer(question, 'routing-test', mock_user_id='1'))
 assert result['type'] == kind
 assert result['saved'] is True
 assert result['sources'] == []
 assert len(saved_payloads) == 1

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
