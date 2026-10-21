"""외부 서버·DB·LLM 없이 JWT 전달, 본인 조회와 대화 저장 연결을 검증합니다."""
import asyncio
import httpx
import pytest

from ai_inquiry import service
from ai_inquiry.clients import backend_client
from ai_inquiry import main as inquiry_main
from fastapi import FastAPI


def test_parking_status_uses_user_server_and_bearer(monkeypatch):
    seen = []
    rows = [{'space_status_code': 'AVAILABLE'}, {'space_status_code': 'OCCUPIED'}]
    def respond(request):
        seen.append(request)
        return httpx.Response(200, json=rows)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(backend_client, 'settings', lambda: {
        'base_url': 'http://test/alpharking/'
    })
    monkeypatch.setattr(backend_client.httpx, 'AsyncClient', lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    result = asyncio.run(backend_client.BackendClient().get_public_parking_spaces('user-test-token'))
    assert result == rows
    assert str(seen[0].url) == 'http://test/alpharking/api/parking/spaces'
    assert seen[0].headers['Authorization'] == 'Bearer user-test-token'


def test_backend_keeps_context_path_and_forwards_bearer(monkeypatch):
    seen = []
    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={"officeId": 2})
    original_client = httpx.AsyncClient
    monkeypatch.setattr(backend_client, 'settings', lambda: {
        'base_url': 'http://test/alpharking/', 'auth_path': 'api/chatbot/me'
    })
    monkeypatch.setattr(backend_client.httpx, 'AsyncClient',
                        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)))
    result = asyncio.run(backend_client.BackendClient().authenticate('test-token'))
    assert result == '2'
    assert str(seen[0].url) == 'http://test/alpharking/api/chatbot/me'
    assert seen[0].headers['Authorization'] == 'Bearer test-token'


@pytest.mark.parametrize('status', [401, 403])
def test_backend_rejects_invalid_authentication(monkeypatch, status):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(backend_client, 'settings', lambda: {
        'base_url': 'http://test/alpharking/', 'auth_path': 'api/chatbot/me'
    })
    monkeypatch.setattr(backend_client.httpx, 'AsyncClient', lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(status))))
    with pytest.raises(PermissionError) as error:
        asyncio.run(backend_client.BackendClient().authenticate('invalid-test-token'))
    assert f'HTTP {status}' in str(error.value)
    assert '/alpharking/api/chatbot/me' in str(error.value)
    assert 'invalid-test-token' not in str(error.value)


@pytest.mark.parametrize('identity', [None, {}, {'officeId': True}, {'officeId': -1},
    {'officeId': None}, {'officeId': 1.5}, {'officeId': 'abc'}, {'officeId': '0'},
    {'officeId': '9223372036854775808'}])
def test_backend_requires_valid_office_identity(monkeypatch, identity):
    async def request(*args, **kwargs):
        return identity
    monkeypatch.setattr(backend_client.BackendClient, 'request', request)
    with pytest.raises(backend_client.BackendError):
        asyncio.run(backend_client.BackendClient().authenticate('test-token'))


@pytest.mark.parametrize('office_id', [2, '2', '9007199254740993'])
def test_backend_accepts_numeric_office_identity_without_rounding(monkeypatch, office_id):
    async def request(*args, **kwargs): return {'officeId': office_id}
    monkeypatch.setattr(backend_client.BackendClient, 'request', request)
    assert asyncio.run(backend_client.BackendClient().authenticate('test-token')) == str(office_id)


@pytest.mark.parametrize('failure,expected', [
    ('status', 'HTTP 500'), ('timeout', '시간 초과'),
    ('connect', '연결 실패'), ('json', 'JSON'),
])
def test_backend_reports_failure_stage_without_credentials(monkeypatch, failure, expected):
    original_client = httpx.AsyncClient
    def respond(request):
        if failure == 'timeout': raise httpx.ReadTimeout('test', request=request)
        if failure == 'connect': raise httpx.ConnectError('test', request=request)
        if failure == 'json': return httpx.Response(200, text='<html>test</html>')
        return httpx.Response(500, text='private server details must not be forwarded')
    monkeypatch.setattr(backend_client, 'settings', lambda: {
        'base_url': 'http://test/alpharking/', 'auth_path': 'api/chatbot/me'
    })
    monkeypatch.setattr(backend_client.httpx, 'AsyncClient', lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    with pytest.raises(backend_client.BackendError) as error:
        asyncio.run(backend_client.BackendClient().authenticate('test-token'))
    assert expected in str(error.value)
    assert 'test-token' not in str(error.value)
    assert 'private server details' not in str(error.value)


@pytest.mark.parametrize('token,office_id', [('account-a', '2'), ('account-b', '3')])
def test_api_answer_uses_authenticated_lookup_and_save(monkeypatch, token, office_id):
    calls = []
    class Backend:
        async def authenticate(self, received):
            assert received == token
            return office_id
        async def get(self, category, received):
            calls.append((category, received))
            return [{'vehicleNumber': 'test-' + office_id, 'entryAt': '2026-10-20T09:00:00'}]
        async def conversation_history(self, received, conversation_id):
            assert received == token and conversation_id == '101'
            return {'messages': [{'senderTypeCode': 'USER', 'content': '이전 질문'}]}
        async def add_conversation(self, received, payload):
            assert received == token
            assert payload['conversationId'] == '101'
            assert 'officeId' not in payload
            assert payload['requestId']
            return {'conversationId': '101', 'answer': payload['answer'], 'type': payload['type'],
                    'sources': payload['sources'], 'saved': True}
    async def generate(question, context, history):
        assert 'test-' + office_id in context
        assert '최근 최대 50건' in context
        assert '이전 질문' in history
        return '본인 조회 결과 테스트'
    def forbidden(*args, **kwargs):
        pytest.fail('API 모드에서는 MOCK 조회와 SQLite 저장을 호출하면 안 됩니다.')
    monkeypatch.setattr(service, 'settings', lambda: {'mode': 'API'})
    monkeypatch.setattr(service, 'BackendClient', Backend)
    monkeypatch.setattr(service, 'generate_answer', generate)
    monkeypatch.setattr(service.MockRepository, 'get', forbidden)
    monkeypatch.setattr(service, 'insert_exchange', forbidden)
    result = asyncio.run(service.answer('내 최근 주차이력 알려줘', '101', token=token))
    assert calls == [('USAGE', token)]
    assert result['saved'] is True
    assert result['conversation_id'] == '101'
    assert result['storage_notice'] is None
    assert result['sources'] == [{'source': 'api:USAGE', 'page': None}]


def test_api_rejects_client_selected_mock_identity(monkeypatch):
    monkeypatch.setattr(service, 'settings', lambda: {'mode': 'API'})
    with pytest.raises(PermissionError):
        asyncio.run(service.answer('내 예약 알려줘', 'test', token='test-token', mock_user_id='1'))


def test_fastapi_requires_and_forwards_bearer_without_loading_vision(monkeypatch):
    app = FastAPI()
    app.include_router(inquiry_main.router)
    monkeypatch.setattr(inquiry_main, 'settings', lambda: {'mode': 'API'})
    called = []
    async def answer(question, conversation, *, token, mock_user_id, request_id):
        called.append(token)
        return {'answer': 'test', 'saved': False, 'storage_notice': 'not stored',
                'conversation_id': conversation, 'type': 'USAGE'}
    monkeypatch.setattr(inquiry_main, 'answer', answer)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            body = {'conversation_id': 'test', 'question': '내 주차이력 알려줘'}
            denied = await client.post('/api/inquiry/chat', json=body)
            assert denied.status_code == 401
            assert called == []
            allowed = await client.post('/api/inquiry/chat', json=body,
                                        headers={'Authorization': 'Bearer test-token'})
            assert allowed.status_code == 200
            assert allowed.json()['saved'] is False
    asyncio.run(run())
    assert called == ['test-token']


def test_first_question_accepts_null_conversation_and_request_uuid(monkeypatch):
    app = FastAPI()
    app.include_router(inquiry_main.router)
    monkeypatch.setattr(inquiry_main, 'settings', lambda: {'mode': 'API'})
    async def answer(question, conversation, *, token, mock_user_id, request_id):
        assert conversation is None
        assert request_id == 'ff4f5590-2259-4b54-aaab-ff81b56a3d88'
        return {'conversation_id': '9007199254740993', 'answer': '저장된 답변', 'saved': True}
    monkeypatch.setattr(inquiry_main, 'answer', answer)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/api/inquiry/chat', headers={'Authorization': 'Bearer test-token'},
                json={'conversation_id': None, 'question': '질문',
                      'request_id': 'ff4f5590-2259-4b54-aaab-ff81b56a3d88'})
            assert response.status_code == 200
            assert response.json()['conversation_id'] == '9007199254740993'
    asyncio.run(run())


@pytest.mark.parametrize('fail_history', [True, False])
def test_history_or_save_failure_never_returns_success(monkeypatch, fail_history):
    class Backend:
        async def authenticate(self, token): return '2'
        async def conversation_history(self, token, conversation_id):
            if fail_history: raise backend_client.BackendError('history denied')
            return {'messages': []}
        async def add_conversation(self, token, payload):
            raise backend_client.BackendError('save failed')
    monkeypatch.setattr(service, 'BackendClient', Backend)
    monkeypatch.setattr(service, 'settings', lambda: {'mode': 'API'})
    with pytest.raises(backend_client.BackendError):
        asyncio.run(service.answer('안녕', '101', token='test-token'))


def test_retry_returns_persisted_answer_and_same_request_id(monkeypatch):
    request_id = 'ff4f5590-2259-4b54-aaab-ff81b56a3d88'
    class Backend:
        async def authenticate(self, token): return '2'
        async def add_conversation(self, token, payload):
            assert payload['requestId'] == request_id
            assert payload['conversationId'] is None
            return {'saved': True, 'conversationId': '101', 'answer': '이미 저장된 답변',
                    'type': 'UNKNOWN', 'sources': []}
    monkeypatch.setattr(service, 'BackendClient', Backend)
    monkeypatch.setattr(service, 'settings', lambda: {'mode': 'API'})
    result = asyncio.run(service.answer('안녕', None, token='test-token', request_id=request_id))
    assert result['answer'] == '이미 저장된 답변'
    assert result['saved'] is True
