"""개발 MOCK 모드에서 실제 INSERT를 확인하는 SQLite. 운영은 Spring Boot POST 사용."""
import sqlite3
from datetime import datetime,timezone
from ai_inquiry.config import settings

def connect():
 con=sqlite3.connect(settings()['mock_db']); con.execute('PRAGMA foreign_keys=ON')
 con.execute('CREATE TABLE IF NOT EXISTS INQUIRY_CONVERSATION (id TEXT PRIMARY KEY, office_id TEXT NOT NULL, created_at TEXT NOT NULL)')
 con.execute('CREATE TABLE IF NOT EXISTS INQUIRY_MESSAGE (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(conversation_id) REFERENCES INQUIRY_CONVERSATION(id))')
 return con

def insert_exchange(office_id, conversation_id, question, answer):
 now=datetime.now(timezone.utc).isoformat()
 with connect() as con:
  row=con.execute('SELECT office_id FROM INQUIRY_CONVERSATION WHERE id=?',(conversation_id,)).fetchone()
  if row and row[0]!=str(office_id): raise PermissionError('다른 회원의 대화입니다.')
  if not row: con.execute('INSERT INTO INQUIRY_CONVERSATION (id,office_id,created_at) VALUES (?,?,?)',(conversation_id,str(office_id),now))
  con.executemany('INSERT INTO INQUIRY_MESSAGE (conversation_id,role,content,created_at) VALUES (?,?,?,?)',[(conversation_id,'USER',question,now),(conversation_id,'ASSISTANT',answer,now)])
 return {'saved':True,'conversation_id':conversation_id}
