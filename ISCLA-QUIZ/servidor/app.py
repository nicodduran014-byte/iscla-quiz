"""Servidor de ISCLA QUIZ. Solo necesita Python 3.10+ y su biblioteca estándar."""
from contextlib import contextmanager
from functools import lru_cache
from hashlib import pbkdf2_hmac, sha256
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from getpass import getpass
import hmac
import json
import mimetypes
import os
import re
import secrets
import socket
import sqlite3
import threading
import time

from vendor.qrencoder import QRCode, QRErrorCorrectLevel

ROOT = Path(__file__).resolve().parent.parent
SEED = Path(__file__).with_name('preguntas.json')
CULTURE_V1_HASH = 'b928938901c7def5568567f6cf2566908759fc05ce3b5d7bf0345afbca4490a1'
CULTURE_UPDATE = 'cultura_general_20_20261119'
CODE = re.compile(r'[A-Z0-9]{6}\Z')
TOKEN = re.compile(r'[A-Za-z0-9_-]{24,80}\Z')
CHARSET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
SESSION_COOKIE = 'iscla_docente'
SESSION_TTL = 12 * 60 * 60
PASSWORD_ITERATIONS = 600_000
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\Z",re.ASCII)
MAX_PLAYERS = 120
MAX_QUESTIONS = 100
QUESTION_MS = 15_000
STATIC_TYPES = {'.css', '.js', '.png', '.jpg', '.webp', '.svg', '.ico', '.woff2'}


class RequestError(Exception):
    def __init__(self, status, message, field=None):
        super().__init__(message)
        self.status, self.field = status, field


def need(condition, status, message, field=None):
    if not condition:
        raise RequestError(status, message, field)


def jd(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def clean(value, limit, field, message, required=True):
    value = value.strip() if isinstance(value, str) else ''
    need((value or not required) and len(value) <= limit, 400, message, field)
    return value


def norm_code(raw):
    return re.sub(r'\s+', '', raw).upper() if isinstance(raw, str) else ''


def token_hash(token):
    return sha256(token.encode('utf-8')).hexdigest()


def password_digest(password, salt):
    return pbkdf2_hmac('sha256',password.encode('utf-8'),salt,PASSWORD_ITERATIONS)


def text_bytes(value):
    if not isinstance(value,str):
        return b''
    try:
        return value.encode('utf-8')
    except UnicodeError:
        return b''


def valid_password(value):
    return isinstance(value,str) and 8 <= len(value) <= 256 and bool(value.strip()) and bool(text_bytes(value))


def ts():
    return int(time.time())


def now_ms():
    return time.time_ns() // 1_000_000


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db=sqlite3.connect(self.path,timeout=8)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript("""
                CREATE TABLE IF NOT EXISTS quizzes (
                  id TEXT PRIMARY KEY, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS seed_updates (
                  id TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS rooms (
                  code TEXT PRIMARY KEY, quiz TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (status IN ('waiting','playing','finished')),
                  created INTEGER NOT NULL, finished INTEGER
                );
                CREATE TABLE IF NOT EXISTS players (
                  id TEXT PRIMARY KEY, room TEXT NOT NULL REFERENCES rooms(code),
                  name TEXT NOT NULL, alias_key TEXT NOT NULL, token TEXT NOT NULL UNIQUE,
                  UNIQUE(room,alias_key)
                );
                CREATE TABLE IF NOT EXISTS answers (
                  player TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                  n INTEGER NOT NULL, selected INTEGER, points INTEGER NOT NULL,
                  timed_out INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(player,n)
                );
                CREATE TABLE IF NOT EXISTS question_clocks (
                  player TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                  n INTEGER NOT NULL, deadline INTEGER NOT NULL,
                  PRIMARY KEY(player,n)
                );
                CREATE TABLE IF NOT EXISTS teachers (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  email TEXT NOT NULL UNIQUE,
                  salt BLOB NOT NULL,
                  digest BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS teacher_sessions (
                  token TEXT PRIMARY KEY, until INTEGER NOT NULL,
                  teacher_id TEXT NOT NULL REFERENCES teachers(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS teacher_sessions_until ON teacher_sessions(until);
            """)
            db.execute('BEGIN IMMEDIATE')
            if 'timed_out' not in {column[1] for column in db.execute('PRAGMA table_info(answers)')}:
                db.execute('ALTER TABLE answers ADD COLUMN timed_out INTEGER NOT NULL DEFAULT 0')
            for quiz in json.loads(SEED.read_text(encoding='utf-8')):
                if quiz['id'] == 'cultura_general':
                    self.seed_culture(db,quiz)
                else:
                    db.execute('INSERT OR IGNORE INTO quizzes(id,body) VALUES(?,?)', (quiz['id'], jd(quiz)))
            db.commit()
        finally:
            db.close()

    @staticmethod
    def seed_culture(db, quiz):
        if db.execute('SELECT 1 FROM seed_updates WHERE id=?',(CULTURE_UPDATE,)).fetchone():
            return
        row = db.execute('SELECT body FROM quizzes WHERE id=?',(quiz['id'],)).fetchone()
        if row is None:
            db.execute('INSERT INTO quizzes(id,body) VALUES(?,?)',(quiz['id'],jd(quiz)))
        else:
            existing = json.loads(row[0])
            canonical = json.dumps(existing,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            if sha256(canonical.encode('utf-8')).hexdigest() == CULTURE_V1_HASH:
                db.execute('UPDATE quizzes SET body=? WHERE id=?',(jd(quiz),quiz['id']))
            elif existing != quiz:
                # Si el docente editó el anterior, conservá su versión y agregá el desafío aparte.
                alternative = dict(quiz,id='cultura_general_desafio',titulo='Cultura general · Desafío')
                db.execute('INSERT OR IGNORE INTO quizzes(id,body) VALUES(?,?)',(alternative['id'],jd(alternative)))
        db.execute('INSERT INTO seed_updates(id) VALUES(?)',(CULTURE_UPDATE,))

    @contextmanager
    def db(self, write=False):
        db = sqlite3.connect(self.path, timeout=8)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _session(db,teacher_id):
        token=secrets.token_urlsafe(32)
        db.execute('DELETE FROM teacher_sessions WHERE until<=?',(ts(),))
        db.execute('INSERT INTO teacher_sessions(token,until,teacher_id) VALUES(?,?,?)',
                   (token_hash(token),ts()+SESSION_TTL,teacher_id))
        return token

    def register_teacher(self,name,email,password):
        salt=secrets.token_bytes(16)
        digest=password_digest(password,salt)
        teacher_id=secrets.token_hex(12)
        with self.db(True) as db:
            need(not db.execute('SELECT 1 FROM teachers WHERE email=?',(email,)).fetchone(),
                 409,'Ya existe una cuenta con ese correo. Usá «Ingresar».','correo')
            db.execute('INSERT INTO teachers VALUES(?,?,?,?,?)',(teacher_id,name,email,salt,digest))
            token=self._session(db,teacher_id)
        return token,{'nombre':name}

    def teachersession(self,teacher_id):
        with self.db(True) as db:
            return self._session(db,teacher_id)

    def teacher_by_email(self,email):
        with self.db() as db:
            return db.execute('SELECT * FROM teachers WHERE email=?',(email,)).fetchone()

    def authentic(self,token):
        if not isinstance(token,str) or not TOKEN.fullmatch(token):
            return None
        with self.db() as db:
            row=db.execute("""
                SELECT t.name FROM teacher_sessions s JOIN teachers t ON t.id=s.teacher_id
                WHERE s.token=? AND s.until>?
            """,(token_hash(token),ts())).fetchone()
        return {'nombre':row['name']} if row else None

    def logout(self,token):
        if isinstance(token,str) and TOKEN.fullmatch(token):
            with self.db(True) as db:
                db.execute('DELETE FROM teacher_sessions WHERE token=?',(token_hash(token),))

    @staticmethod
    def quiz(db, id):
        row = db.execute('SELECT body FROM quizzes WHERE id=?', (id,)).fetchone()
        return json.loads(row['body']) if row else None

    def save_quiz(self, body):
        id = body.get('id') or None
        data = {
            'titulo':clean(body.get('titulo'),80,'titulo','Ingresá un nombre de hasta 80 caracteres.'),
            'materia':clean(body.get('materia'),60,'materia','Ingresá una materia de hasta 60 caracteres.'),
            'autor':clean(body.get('autor'),60,'autor','Ingresá un autor de hasta 60 caracteres.')
        }
        with self.db(True) as db:
            prev = self.quiz(db,id) if isinstance(id,str) else None
            need(not id or prev,404,'Ese cuestionario ya no está disponible.')
            data.update(id=id or secrets.token_hex(12),preguntas=prev['preguntas'] if prev else [])
            db.execute('INSERT OR REPLACE INTO quizzes(id,body) VALUES(?,?)', (data['id'], jd(data)))
        return data

    def save_question(self, body, delete=False):
        quiz_id = clean(body.get('quiz'),80,'quiz','Seleccioná un cuestionario.')
        id = clean(body.get('id'),80,'id','Pregunta inválida.',False)
        origin = clean(body.get('origen'),80,'quiz','Cuestionario inválido.',False) or quiz_id
        with self.db(True) as db:
            dest = self.quiz(db,quiz_id)
            need(dest,404,'Seleccioná un cuestionario.', 'quiz')
            source = dest if origin == quiz_id else self.quiz(db,origin)
            idx = next((i for i, q in enumerate(source['preguntas']) if q['id'] == id), -1) if source else -1
            need(not (id or delete) or idx >= 0,404,'Esa pregunta ya no está disponible.')
            if delete:
                source['preguntas'].pop(idx)
            else:
                question = dict(
                    id=id or secrets.token_hex(12),
                    texto=clean(body.get('texto'),300,'texto','Escribí un enunciado de hasta 300 caracteres.'),
                    tema=clean(body.get('tema'),70,'tema','El tema admite hasta 70 caracteres.',False)
                )
                options = body.get('opciones')
                need(isinstance(options,list) and len(options) == 4,400,'Completá las cuatro opciones.','opA')
                options = [clean(a,180,'op'+'ABCD'[n],'Completá las cuatro opciones, con hasta 180 caracteres cada una.') for n,a in enumerate(options)]
                need(len({a.casefold() for a in options}) == 4,400,'Las opciones deben ser diferentes.','opA')
                correct = body.get('correcta')
                need(type(correct) is int and 0 <= correct <= 3,400,'Marcá la opción correcta.','correcta')
                question.update(opciones=options,correcta=correct)
                previous_explanation = source['preguntas'][idx].get('explicacion','') if idx >= 0 else ''
                explanation = clean(body.get('explicacion',previous_explanation),180,'explicacion',
                                    'La explicación admite hasta 180 caracteres.',False)
                if explanation:
                    question['explicacion'] = explanation
                if source is dest and idx >= 0:
                    dest['preguntas'][idx] = question
                else:
                    need(len(dest['preguntas']) < MAX_QUESTIONS,400,'El cuestionario alcanzó su límite de preguntas.')
                    if idx >= 0:
                        source['preguntas'].pop(idx)
                    dest['preguntas'].append(question)
            for quiz in ([dest] if source is dest or not source else [source,dest]):
                db.execute('UPDATE quizzes SET body=? WHERE id=?', (jd(quiz),quiz['id']))
        return {'ok':True}

    def panel(self):
        with self.db() as db:
            quizzes = [json.loads(r['body']) for r in db.execute('SELECT body FROM quizzes ORDER BY rowid')]
            rows = db.execute('''SELECT r.*, (SELECT COUNT(*) FROM players WHERE room=r.code) n
                                 FROM rooms r ORDER BY created DESC, rowid DESC''').fetchall()
            rooms = [{'code':r['code'],'status':r['status'],'quiz':{'titulo':json.loads(r['quiz'])['titulo']},'count':r['n']} for r in rows]
        return {'quizzes':quizzes,'rooms':rooms}

    @staticmethod
    def room_row(db, code):
        need(CODE.fullmatch(code),400,'Ingresá el código de 6 caracteres que te dio el docente.','codigo')
        row = db.execute('SELECT * FROM rooms WHERE code=?', (code,)).fetchone()
        need(row,404,'No encontramos esa partida. Revisá el código o volvé a escanear el QR.','codigo')
        return row

    @staticmethod
    def player(db, code, token):
        if not TOKEN.fullmatch(token or ''):
            return None
        return db.execute('SELECT * FROM players WHERE room=? AND token=?', (code,token_hash(token))).fetchone()

    def new_room(self, quiz_id, total):
        with self.db(True) as db:
            quiz = self.quiz(db,quiz_id) if isinstance(quiz_id,str) else None
            need(quiz and quiz['preguntas'],400,'Elegí un cuestionario con preguntas.','quiz')
            all_q = quiz['preguntas']
            need(total is None or type(total) is int and 1 <= total <= len(all_q),400,'Elegí una cantidad de preguntas disponible.','cantidad')
            quiz['preguntas'] = all_q if total is None else all_q[:total]
            while True:
                code = ''.join(secrets.choice(CHARSET) for _ in range(6))
                if re.search('[A-Z]',code) and re.search('[0-9]',code) and not db.execute('SELECT 1 FROM rooms WHERE code=?',(code,)).fetchone():
                    break
            db.execute('INSERT INTO rooms(code,quiz,status,created) VALUES(?,?,?,?)',(code,jd(quiz),'waiting',ts()))
        return self.room(code,True)

    def join(self, code, raw_name, old_token):
        with self.db(True) as db:
            room = self.room_row(db,code)
            if self.player(db,code,old_token):
                return {'code':code,'token':old_token}
            need(room['status']=='waiting',409,'El ingreso a esta partida ya cerró. Pedile un código nuevo al docente.','codigo')
            name = clean(raw_name,30,'alias','Ingresá un alias de hasta 30 caracteres.')
            need(not db.execute('SELECT 1 FROM players WHERE room=? AND alias_key=?',(code,name.casefold())).fetchone(),
                 409,'Ese alias ya está ocupado. Elegí otro.','alias')
            count = db.execute('SELECT COUNT(*) FROM players WHERE room=?',(code,)).fetchone()[0]
            need(count < MAX_PLAYERS,409,'La sala alcanzó el máximo de participantes.')
            token = secrets.token_urlsafe(24)
            db.execute('INSERT INTO players VALUES(?,?,?,?,?)',(secrets.token_hex(12),code,name,name.casefold(),token_hash(token)))
        return {'code':code,'token':token}

    def set_state(self, code, status):
        with self.db(True) as db:
            room = self.room_row(db,code)
            if room['status'] == status:
                return
            prior = 'waiting' if status == 'playing' else 'playing'
            need(room['status']==prior,409,'La partida ya cambió de estado.')
            need(db.execute('SELECT 1 FROM players WHERE room=?',(code,)).fetchone(),409,'Esperá a que ingrese al menos un estudiante.')
            db.execute('UPDATE rooms SET status=?,finished=? WHERE code=?',(status,ts() if status=='finished' else None,code))

    def leave(self, code, token):
        with self.db(True) as db:
            room = self.room_row(db,code)
            player = self.player(db,code,token)
            if player and room['status']=='waiting':
                db.execute('DELETE FROM players WHERE id=?',(player['id'],))
        return {'ok':True}

    @staticmethod
    def answer_payload(selected, points, timed_out):
        return {'points':points,'selected':selected,**({'timed_out':True} if timed_out else {})}

    def open_question(self, code, token, n):
        with self.db(True) as db:
            room = self.room_row(db,code)
            player = self.player(db,code,token)
            need(player,403,'Ingresá a la partida para ver la pregunta.')
            questions = json.loads(room['quiz'])['preguntas']
            need(type(n) is int and 0 <= n < len(questions),400,'La pregunta no está disponible.')
            count = db.execute('SELECT COUNT(*) FROM answers WHERE player=?',(player['id'],)).fetchone()[0]
            need(room['status']=='playing' and n==count,409,'Esta pregunta ya no está habilitada.')
            key = (player['id'],n)
            clock = db.execute('SELECT deadline FROM question_clocks WHERE player=? AND n=?',key).fetchone()
            now = now_ms()
            deadline = clock['deadline'] if clock else now + QUESTION_MS
            if clock is None:
                db.execute('INSERT INTO question_clocks(player,n,deadline) VALUES(?,?,?)',(*key,deadline))
            question = {k:questions[n][k] for k in ('id','texto','tema','opciones') if k in questions[n]}
            return {'durationMs':QUESTION_MS,'remainingMs':max(0,min(QUESTION_MS,deadline-now)),'question':question}

    def answer(self, code, token, n, selected, received):
        with self.db(True) as db:
            room = self.room_row(db,code)
            player = self.player(db,code,token)
            need(player,403,'Ingresá a la partida para responder.')
            qs = json.loads(room['quiz'])['preguntas']
            need(type(n) is int and 0 <= n < len(qs),400,'La pregunta no está disponible.')
            need(selected is None or type(selected) is int and 0 <= selected <= 3,400,'Elegí una opción válida.')
            answers = db.execute('SELECT * FROM answers WHERE player=? ORDER BY n',(player['id'],)).fetchall()
            if n < len(answers):
                saved = answers[n]
                return self.answer_payload(saved['selected'],saved['points'],saved['timed_out'])
            need(room['status']=='playing' and n==len(answers),409,'Esta pregunta ya no está habilitada.')
            clock = db.execute('SELECT deadline FROM question_clocks WHERE player=? AND n=?',(player['id'],n)).fetchone()
            need(clock,409,'Abrí la pregunta para empezar a responder.')
            timed_out = received >= clock['deadline']
            if timed_out:
                selected = None
            points = 100 if selected == qs[n]['correcta'] else 0
            db.execute('INSERT INTO answers(player,n,selected,points,timed_out) VALUES(?,?,?,?,?)',
                       (player['id'],n,selected,points,timed_out))
            remaining = db.execute('''SELECT 1 FROM players p WHERE p.room=? AND
                (SELECT COUNT(*) FROM answers a WHERE a.player=p.id)<? LIMIT 1''',(code,len(qs))).fetchone()
            if not remaining:
                db.execute("UPDATE rooms SET status='finished',finished=? WHERE code=?",(ts(),code))
        return self.answer_payload(selected,points,timed_out)

    def room(self, code, teacher=False, token=''):
        with self.db() as db:
            row=self.room_row(db,code)
            if not teacher:
                player=self.player(db,code,token)
                need(player,403,'Entrá con el código y tu alias para ver esta partida.')
            else:
                player=None
            players = db.execute('''SELECT p.id,p.name,COUNT(a.n) answered,COALESCE(SUM(a.points),0) score
                FROM players p LEFT JOIN answers a ON a.player=p.id WHERE p.room=?
                GROUP BY p.id ORDER BY p.rowid''',(code,)).fetchall()
            quiz=json.loads(row['quiz'])
            allowed=[None]*len(quiz['preguntas'])
            own = []
            if player:
                own = [self.answer_payload(r['selected'],r['points'],r['timed_out'])
                       for r in db.execute('SELECT selected,points,timed_out FROM answers WHERE player=? ORDER BY n',(player['id'],))]
                if row['status'] != 'waiting':
                    allowed[:len(own)] = quiz['preguntas'][:len(own)]
            return dict(code=code,status=row['status'], quiz=dict(titulo=quiz['titulo'],materia=quiz['materia'],preguntas=allowed),
                        players=[dict(r) for r in players], me=player['id'] if player else None, answers=own)

def ipv4_lan():
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1',9))  # El sistema elige una interfaz, sin enviar paquetes.
            ip=sock.getsockname()[0]
            if not ip_address(ip).is_loopback:
                return ip
    except OSError:
        pass
    try:
        return next((ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip_address(ip).is_loopback),None)
    except OSError:
        return None


@lru_cache(maxsize=192)
def qr_svg(url):
    qr=QRCode(None,QRErrorCorrectLevel.M)
    qr.addData(url)
    qr.make()
    n=qr.getModuleCount()
    path=''.join(f'M{x+4} {y+4}h1v1h-1z' for y in range(n) for x in range(n) if qr.isDark(y,x))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n+8} {n+8}" shape-rendering="crispEdges"><path fill="#fff" d="M0 0h{n+8}v{n+8}H0z"/><path fill="#000" d="{path}"/></svg>'.encode()


def public_origin(value):
    if not value:
        return ''
    parsed=urlsplit(value)
    ok=(parsed.scheme in ('http','https') and parsed.hostname and not parsed.username and not parsed.password
        and not parsed.query and not parsed.fragment and parsed.path in ('','/') and len(parsed.netloc)<=180
        and re.fullmatch(r'[A-Za-z0-9.\-:\[\]]+',parsed.netloc))
    if not ok:
        raise ValueError('ISCLA_URL_PUBLICA debe ser un origen como https://quiz.ejemplo.edu.ar, sin ruta.')
    _=parsed.port
    return parsed.scheme+'://'+parsed.netloc


class App(ThreadingHTTPServer):
    daemon_threads=True

    def __init__(self,address,db_path,invite_code,origin=''):
        self.store=Store(db_path)
        self.invite_digest=sha256(invite_code.encode('utf-8')).digest()
        self.dummy_salt=secrets.token_bytes(16)
        self.public_origin=public_origin(origin)
        self.https=self.public_origin.startswith('https://')
        self.lan_ip=ipv4_lan()
        self.attempts={}
        self.auth_lock=threading.Lock()
        self.auth_slots=threading.BoundedSemaphore(4)
        super().__init__(address,Handler)

    @contextmanager
    def auth_attempt(self, ip, action):
        key, aggregate = (action,ip), (action,'*')
        with self.auth_lock:
            now=time.monotonic()
            self.attempts={key:tries for key,tries in self.attempts.items() if tries[0]>now}
            until,attempts=self.attempts.get(key,(now+120,0))
            window,all_attempts=self.attempts.get(aggregate,(now+120,0))
            need(attempts<10 and all_attempts<50,429,'Hubo varios intentos. Esperá dos minutos y volvé a intentar.')
            need(self.auth_slots.acquire(blocking=False),429,'Hay varias solicitudes en curso. Volvé a intentar en unos segundos.')
            self.attempts[key]=(until,attempts+1)
            self.attempts[aggregate]=(window,all_attempts+1)
        try:
            yield
        except RequestError:
            raise
        else:
            with self.auth_lock:
                for k in (key,aggregate):
                    current=self.attempts.get(k)
                    if current:
                        self.attempts[k]=(current[0],max(0,current[1]-1))
        finally:
            self.auth_slots.release()

    def login(self,ip,email,password):
        email=email.strip().lower() if isinstance(email,str) and len(email)<=254 else ''
        password=password if valid_password(password) else ''
        with self.auth_attempt(ip,'login'):
            teacher=self.store.teacher_by_email(email)
            digest=password_digest(password,teacher['salt'] if teacher else self.dummy_salt)
            matched=hmac.compare_digest(digest,teacher['digest'] if teacher else b'\x00'*len(digest))
            need(teacher and matched,401,'El correo o la contraseña no son correctos.','clave')
        return self.store.teachersession(teacher['id']),{'nombre':teacher['name']}

    def register(self,ip,data):
        name=clean(data.get('nombre'),80,'nombre','Ingresá tu nombre y apellido (hasta 80 caracteres).')
        need(text_bytes(name) and not any(ord(c)<32 for c in name),400,'Ingresá un nombre válido.','nombre')
        email=clean(data.get('correo'),254,'correo','Ingresá un correo electrónico válido.').lower()
        need(EMAIL.fullmatch(email),400,'Ingresá un correo electrónico válido.','correo')
        password=data.get('clave')
        need(valid_password(password),400,'Usá entre 8 y 256 caracteres para la contraseña.','clave')
        need(password==data.get('confirmacion'),400,'Las contraseñas no coinciden.','confirmacion')
        code=clean(data.get('codigo'),128,'codigo','Ingresá el código de registro que te dio la institución.')
        with self.auth_attempt(ip,'registro'):
            matches=hmac.compare_digest(sha256(text_bytes(code)).digest(),self.invite_digest)
            need(matches,403,'El código de registro no es correcto. Consultalo con tu institución.','codigo')
            return self.store.register_teacher(name,email,password)


class Handler(BaseHTTPRequestHandler):
    server_version='ISCLAQuiz'
    sys_version=''

    @property
    def store(self):
        return self.server.store

    def setup(self):
        super().setup()
        self.connection.settimeout(12)

    def log_message(self, format, *args):
        # No registrar aliases, sesiones, contraseñas ni consultas del URL.
        pass

    def body(self):
        need(self.headers.get('X-ISCLA-Request')=='1',403,'Solicitud no válida.')
        need(self.headers.get('Sec-Fetch-Site') not in ('cross-site','same-site'),403,'Solicitud no válida.')
        need(self.headers.get('Content-Type','').split(';')[0].strip().lower()=='application/json',415,'Formato de solicitud no válido.')
        n=self.headers.get('Content-Length','')
        need(n.isascii() and n.isdigit() and len(n)<=5 and 0<int(n)<=24_000,413,'La solicitud supera el tamaño permitido.')
        try:
            data=json.loads(self.rfile.read(int(n)))
            if isinstance(data,dict):
                return data
        except (ValueError,UnicodeError):
            pass
        raise RequestError(400,'Solicitud no válida.')

    def teacher_token(self):
        jar=SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie',''))
        except CookieError:
            return ''
        return jar[SESSION_COOKIE].value if SESSION_COOKIE in jar else ''

    def student_token(self):
        token=self.headers.get('X-ISCLA-Student','')
        return token if TOKEN.fullmatch(token) else ''

    def staff(self):
        need(self.store.authentic(self.teacher_token()),401,'Iniciá sesión como docente para continuar.')

    def cookie(self, value='', age=0):
        secure='; Secure' if self.server.https else ''
        return f'{SESSION_COOKIE}={value}; Max-Age={age}; Path=/; HttpOnly; SameSite=Strict{secure}'

    def send(self, payload, mime, status=200, extra=(), cache='no-store', head=False):
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control',cache)
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; connect-src 'self'")
        for k,v in extra:
            self.send_header(k,v)
        self.end_headers()
        if not head:
            self.wfile.write(payload)

    def response(self, obj, status=200, headers=()):
        self.send(jd(obj).encode(), 'application/json; charset=utf-8',status,headers)

    def invitation(self, code):
        origin=self.server.public_origin
        if not origin:
            raw=self.headers.get('Host','')
            parsed=urlsplit('//'+raw)
            host=parsed.hostname
            if not host or not re.fullmatch(r'[A-Za-z0-9.\-:\[\]]{1,180}',raw):
                host=None
            if host in ('localhost','127.0.0.1','::1') or not host:
                ip=self.server.lan_ip
                host=ip or '127.0.0.1'
                authority=f'{host}:{self.server.server_port}'
            else:
                authority=raw
            origin='http://'+authority
        return origin+'/templates/acceso.html?codigo='+quote(code,safe='')

    def room_for_staff(self, code):
        self.staff()
        r=self.store.room(code,True)
        r.update(joinUrl=self.invitation(code),qrPath='/api/partidas/'+code+'/qr.svg')
        return r

    def api(self, path, method):
        if method=='GET':
            if path=='/api/health':
                return self.response({'status':'ok'})
            if path=='/api/session':
                teacher=self.store.authentic(self.teacher_token())
                return self.response({'teacher':True,'docente':teacher} if teacher else {'teacher':False})
            if path=='/api/panel':
                self.staff()
                return self.response(self.store.panel())
            match=re.fullmatch(r'/api/partidas/([A-Z0-9]{6})(/docente|/qr\.svg)?',path)
            if match:
                code, action=match.groups()
                if action=='/docente':
                    return self.response(self.room_for_staff(code))
                if action=='/qr.svg':
                    room=self.room_for_staff(code)
                    return self.send(qr_svg(room['joinUrl']),'image/svg+xml; charset=utf-8')
                return self.response(self.store.room(code,token=self.student_token()))
        if method=='POST':
            data=self.body()
            if path in ('/api/login','/api/registro'):
                registering=path=='/api/registro'
                if registering:
                    token,teacher=self.server.register(self.client_address[0],data)
                else:
                    token,teacher=self.server.login(self.client_address[0],data.get('correo'),data.get('clave'))
                self.store.logout(self.teacher_token())
                return self.response({'teacher':True,'docente':teacher},201 if registering else 200,
                                     headers=[('Set-Cookie',self.cookie(token,SESSION_TTL))])
            if path=='/api/logout':
                self.store.logout(self.teacher_token())
                return self.response({'teacher':False},headers=[('Set-Cookie',self.cookie())])
            if path=='/api/cuestionarios':
                self.staff()
                return self.response(self.store.save_quiz(data))
            if path in ('/api/preguntas','/api/preguntas/eliminar'):
                self.staff()
                return self.response(self.store.save_question(data,path.endswith('/eliminar')))
            if path=='/api/partidas':
                self.staff()
                r=self.store.new_room(data.get('quiz'),data.get('cantidad'))
                r.update(joinUrl=self.invitation(r['code']),qrPath='/api/partidas/'+r['code']+'/qr.svg')
                return self.response(r,201)
            if path=='/api/unirse':
                return self.response(self.store.join(norm_code(data.get('codigo')),data.get('alias'),self.student_token()))
            match=re.fullmatch(r'/api/partidas/([A-Z0-9]{6})/(iniciar|cerrar|pregunta|responder|salir)',path)
            if match:
                code, action=match.groups()
                if action in ('iniciar','cerrar'):
                    self.staff()
                    self.store.set_state(code,'playing' if action=='iniciar' else 'finished')
                    return self.response(self.room_for_staff(code))
                if action=='pregunta':
                    return self.response(self.store.open_question(code,self.student_token(),data.get('pregunta')))
                if action=='responder':
                    need('opcion' in data,400,'Falta indicar la respuesta.')
                    return self.response(self.store.answer(code,self.student_token(),data.get('pregunta'),data['opcion'],now_ms()))
                return self.response(self.store.leave(code,self.student_token()))
        raise RequestError(404,'No encontramos ese recurso.')

    def static_file(self, path, head=False):
        if path in ('/','/index.html'):
            file=ROOT/'index.html'
        elif re.fullmatch(r'/templates/[a-z]+\.html',path):
            file=ROOT/path[1:]
        elif re.fullmatch(r'/static/(css|js|img)/[A-Za-z0-9._-]+',path):
            file=ROOT/path[1:]
            need(file.suffix in STATIC_TYPES,404,'Recurso no disponible.')
        else:
            raise RequestError(404,'No encontramos esa página.')
        need(file.is_file() and file.resolve().is_relative_to(ROOT),404,'No encontramos esa página.')
        mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        if file.suffix in ('.html','.css','.js','.svg'):
            mime+='; charset=utf-8'
        return self.send(file.read_bytes(),mime,head=head,cache='no-store' if file.suffix=='.html' else 'no-cache')

    def handle_http(self, method):
        try:
            path=unquote(urlsplit(self.path).path)
            if path.startswith('/api/'):
                return self.api(path,method)
            need(method in ('GET','HEAD'),405,'Método no permitido.')
            return self.static_file(path,method=='HEAD')
        except RequestError as error:
            return self.response({'message':str(error),'field':error.field},error.status)
        except (BrokenPipeError,ConnectionError,TimeoutError):
            return None
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                self.response({'message':'No se pudo completar la solicitud. Volvé a intentar.'},500)
            except OSError:
                pass

    def do_GET(self): self.handle_http('GET')
    def do_HEAD(self): self.handle_http('HEAD')
    def do_POST(self): self.handle_http('POST')


def main():
    invite_code=os.environ.get('ISCLA_CODIGO_DOCENTE','').strip()
    if not invite_code:
        try:
            invite_code=getpass('Definí el código de registro docente (al menos 8 caracteres): ').strip()
        except (EOFError,KeyboardInterrupt):
            raise SystemExit('Definí ISCLA_CODIGO_DOCENTE o ingresá un código para iniciar.')
    if not 8 <= len(invite_code) <= 128:
        raise SystemExit('El código de registro docente debe tener entre 8 y 128 caracteres.')
    host=os.environ.get('ISCLA_HOST','0.0.0.0')
    port=int(os.environ.get('PORT','8000'))
    db_path=os.environ.get('ISCLA_DB',str(ROOT/'datos'/'iscla.sqlite3'))
    with App((host,port),db_path,invite_code,os.environ.get('ISCLA_URL_PUBLICA','')) as server:
        print(f'\nISCLA QUIZ en http://localhost:{server.server_port}/',flush=True)
        if server.public_origin:
            print(f'Dirección para compartir: {server.public_origin}/',flush=True)
        elif server.lan_ip:
            print(f'Desde el mismo Wi-Fi: http://{server.lan_ip}:{server.server_port}/',flush=True)
        print('Dejá esta ventana abierta durante la partida. Ctrl+C para detener.\n',flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__=='__main__':
    main()
