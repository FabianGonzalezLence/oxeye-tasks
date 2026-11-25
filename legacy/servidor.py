#!/usr/bin/env python3
"""OxEye · Trabajo compartido — servidor local, sin dependencias externas.
    Python 3.9+ · SQLite · sesiones por usuario · API JSON · adjuntos.
"""
import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'datos'
FILES = DATA / 'adjuntos'
DB = DATA / 'oxeye.sqlite3'
MAX_BODY = 20 * 1024 * 1024
MAX_FILE = 15 * 1024 * 1024
ALLOWED_EXT = {'.pdf','.txt','.md','.csv','.json','.docx','.xlsx','.pptx','.png','.jpg','.jpeg','.webp','.svg','.gif','.zip','.7z','.step','.stp','.stl','.glb','.obj','.dxf','.dwg','.skp','.html'}
ROLES = {'admin', 'desarrollo', 'revision'}
LOCK = threading.RLock()

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def connection():
    conn = sqlite3.connect(str(DB), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def hash_pass(password, salt=None):
    salt = salt or secrets.token_bytes(18)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 330_000)
    return base64.b64encode(salt).decode() + ':' + base64.b64encode(h).decode()

def verify_pass(password, hashed):
    try:
        salt, digest = hashed.split(':',1)
        comp = hash_pass(password, base64.b64decode(salt))
        return hmac.compare_digest(comp, hashed)
    except Exception:
        return False

def get_rev(conn):
    return conn.execute("SELECT value FROM meta WHERE name='revision'").fetchone()['value']

def bump(conn):
    conn.execute("UPDATE meta SET value=value+1 WHERE name='revision'")

def audit(conn, actor, action, taskid=None, detail=''):
    conn.execute("INSERT INTO audit(actor,action,task_id,detail,created_at) VALUES(?,?,?,?,?)", (actor,action,taskid,detail[:1200],now()))
    bump(conn)

def initialize():
    DATA.mkdir(exist_ok=True)
    FILES.mkdir(exist_ok=True)
    with LOCK, connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
            id TEXT PRIMARY KEY, type TEXT NOT NULL CHECK(type IN ('feature','fix')),
            title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', why TEXT NOT NULL DEFAULT '',
            acceptance TEXT NOT NULL DEFAULT '', depends TEXT NOT NULL DEFAULT '', chapter TEXT NOT NULL DEFAULT '',
            phase TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'P1',
            owner TEXT NOT NULL DEFAULT '', frustration INTEGER CHECK(frustration BETWEEN 1 AND 10),
            author_effort INTEGER CHECK(author_effort BETWEEN 1 AND 10),
            dev_effort INTEGER CHECK(dev_effort BETWEEN 1 AND 10), dev_response TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','review','history')),
            version INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL, updated_by TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS comments(
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
            author TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attachments(
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
            original_name TEXT NOT NULL, storage_name TEXT NOT NULL, mime TEXT NOT NULL,
            size INTEGER NOT NULL, uploaded_by TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
            task_id TEXT, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value INTEGER NOT NULL);
        INSERT OR IGNORE INTO meta(name,value) VALUES('revision',1);
        CREATE INDEX IF NOT EXISTS ix_task_status ON tasks(status,updated_at);
        CREATE INDEX IF NOT EXISTS ix_comment_task ON comments(task_id);
        CREATE INDEX IF NOT EXISTS ix_attachment_task ON attachments(task_id);
        ''')
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            password = secrets.token_urlsafe(12)
            db.execute("INSERT INTO users(username,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?)", ('admin','Dirección','admin',hash_pass(password),now()))
            key_file = DATA / 'ACCESO_INICIAL.txt'
            key_file.write_text('OXEYE — PRIMER ACCESO\n\nUsuario: admin\nContraseña: '+password+'\n\nEntrar en la dirección que muestre la terminal.\nCambiar la contraseña desde la aplicación. No publicar esta clave.\n',encoding='utf-8')
            try: key_file.chmod(0o600)
            except Exception: pass
            print('\n  PRIMER ACCESO\n  Usuario: admin\n  Contraseña: '+password+'\n  Copia guardada en datos/ACCESO_INICIAL.txt\n')
        if db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 0:
            seed = ROOT / 'tareas_iniciales.json'
            if seed.exists():
                tasks=json.loads(seed.read_text(encoding='utf-8'))
                for x in tasks:
                    db.execute('''INSERT INTO tasks(id,type,title,description,why,acceptance,depends,chapter,phase,priority,owner,created_by,updated_by,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        x['id'],'fix' if any(w in (x.get('title','')+' '+x.get('work','')).lower() for w in ('corregir bug','reparar error','solventar fallo')) else 'feature',
                        x['title'],x.get('work',''),x.get('why',''),x.get('check',''),x.get('depends',''),x.get('chapter',''),x.get('phase',''),x.get('priority','P1'),x.get('owner',''),
                        'Importación original','Importación original',now(),now()))
                audit(db,'Sistema','importacion-inicial',None,f'{len(tasks)} tareas originales del HTML previo')
        db.commit()

def rowdict(row):
    return dict(row) if row else None

def public_user(r):
    return {k:r[k] for k in ('id','username','display_name','role')} if r else None

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    server_version='OxEyeWork/1.0'

    def log_message(self, fmt,*args):
        if 'GET /api/snapshot' not in fmt and 'GET /api/me' not in fmt:
            super().log_message(fmt,*args)

    def baseheaders(self, status, length, contenttype='application/json; charset=utf-8', extra=None):
        self.send_response(status)
        self.send_header('Content-Type',contenttype)
        self.send_header('Content-Length',str(length))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        if extra:
            for k,v in extra.items(): self.send_header(k,v)
        self.end_headers()

    def send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False,default=str).encode('utf-8')
        self.baseheaders(status,len(body))
        self.wfile.write(body)

    def error(self,code,message,**extra):
        self.send_json(code,{'error':message,**extra})

    def auth(self, conn):
        h=self.headers.get('Authorization','')
        if not h.startswith('Bearer '):return None
        token=h[7:]
        r=conn.execute('''SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
          WHERE sessions.token=? AND sessions.expires_at>?''',(token,int(time.time()))).fetchone()
        return r

    def require(self, conn, roles=None):
        user=self.auth(conn)
        if not user:
            self.error(401,'Inicia sesión para acceder a los datos compartidos.')
            return None
        if roles and user['role'] not in roles:
            self.error(403,'Tu perfil no permite realizar esta acción.')
            return None
        return user

    def getbody(self):
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: raise ValueError('Tamaño de petición inválido.')
        if length>MAX_BODY: raise ValueError('El archivo supera el límite de 15 MB.')
        if length < 1: return b''
        return self.rfile.read(length)

    def jsonbody(self):
        raw=self.getbody()
        try: data=json.loads(raw)
        except Exception: raise ValueError('JSON inválido.')
        if not isinstance(data,dict): raise ValueError('Se esperaba un objeto JSON.')
        return data

    def task_detail(self, db, tid):
        r=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
        if not r:return None
        d=rowdict(r)
        d['comments']=[rowdict(x) for x in db.execute('SELECT * FROM comments WHERE task_id=? ORDER BY created_at ASC,id ASC',(tid,))]
        d['attachments']=[{k:x[k] for k in ('id','original_name','mime','size','uploaded_by','created_at')} for x in db.execute('SELECT * FROM attachments WHERE task_id=? ORDER BY created_at DESC',(tid,))]
        d['activity']=[rowdict(x) for x in db.execute('SELECT * FROM audit WHERE task_id=? ORDER BY id DESC LIMIT 30',(tid,))]
        return d

    def do_GET(self):
        path=unquote(urlsplit(self.path).path)
        if path in ('/','/index.html'):
            data=(ROOT/'index.html').read_bytes()
            self.baseheaders(200,len(data),'text/html; charset=utf-8')
            self.wfile.write(data);return
        if path=='/favicon.ico':
            self.baseheaders(204,0);return
        if not path.startswith('/api/'):
            self.error(404,'No encontrado.');return
        with connection() as db:
            user=self.require(db)
            if not user:return
            if path=='/api/me':
                self.send_json(200,{'user':public_user(user)});return
            if path=='/api/users':
                self.send_json(200,{'users':[public_user(x) for x in db.execute('SELECT * FROM users ORDER BY display_name')]});return
            if path=='/api/snapshot':
                rows=db.execute('''SELECT tasks.*,
                    (SELECT COUNT(*) FROM attachments WHERE attachments.task_id=tasks.id) AS files_count,
                    (SELECT COUNT(*) FROM comments WHERE comments.task_id=tasks.id) AS comments_count
                    FROM tasks ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'review' THEN 1 ELSE 2 END,
                    CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, updated_at DESC''').fetchall()
                self.send_json(200,{'revision':get_rev(db),'tasks':[rowdict(x) for x in rows], 'time':now()});return
            if path.startswith('/api/tasks/'):
                tid=path[len('/api/tasks/'):].strip('/')
                if not tid or '/' in tid: self.error(404,'No encontrado.');return
                d=self.task_detail(db,tid)
                self.send_json(200,{'task':d}) if d else self.error(404,'No existe la tarea.');return
            if path.startswith('/api/files/'):
                fid=path[len('/api/files/'):]
                r=db.execute('SELECT * FROM attachments WHERE id=?',(fid,)).fetchone()
                if not r:self.error(404,'No existe el archivo.');return
                f=FILES/r['storage_name']
                if not f.is_file():self.error(404,'Archivo no disponible.');return
                data=f.read_bytes()
                name=r['original_name'].replace('"','').replace('\n','')
                self.baseheaders(200,len(data),'application/octet-stream',{'Content-Disposition':f'attachment; filename="download"; filename*=UTF-8\'\'{__import__("urllib.parse",fromlist=["quote"]).quote(name)}'})
                self.wfile.write(data);return
            if path=='/api/export':
                data={'exported_at':now(),'tasks':[self.task_detail(db,x['id']) for x in db.execute('SELECT id FROM tasks ORDER BY created_at')],
                      'users':[public_user(x) for x in db.execute('SELECT * FROM users')],
                      'note':'La exportación JSON contiene los datos y metadatos, no los bytes de los adjuntos. Haz una copia de la carpeta datos/ para respaldo completo.'}
                raw=json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8')
                self.baseheaders(200,len(raw),'application/json; charset=utf-8',{'Content-Disposition':'attachment; filename="oxeye_trabajo_export.json"'})
                self.wfile.write(raw);return
        self.error(404,'Ruta no encontrada.')

    def do_POST(self):
        path=urlsplit(self.path).path
        try:
            if path=='/api/login':
                d=self.jsonbody()
                username=str(d.get('username','')).strip().lower()
                password=str(d.get('password',''))
                with LOCK,connection() as db:
                    u=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                    if not u or not verify_pass(password,u['password_hash']):
                        self.error(401,'Usuario o contraseña incorrectos.');return
                    token=secrets.token_urlsafe(40)
                    db.execute('INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)',(token,u['id'],int(time.time())+60*60*24*21))
                    db.commit()
                    self.send_json(200,{'token':token,'user':public_user(u)});return
            with LOCK,connection() as db:
                user=self.require(db)
                if not user:return
                actor=user['display_name']
                if path=='/api/logout':
                    tok=self.headers.get('Authorization','')[7:]
                    db.execute('DELETE FROM sessions WHERE token=?',(tok,));db.commit()
                    self.send_json(200,{'ok':True});return
                if path=='/api/users':
                    if user['role']!='admin': self.error(403,'Solo la dirección puede dar de alta usuarios.');return
                    d=self.jsonbody()
                    username=str(d.get('username','')).strip().lower()
                    display=str(d.get('display_name','')).strip()
                    role=str(d.get('role','desarrollo'))
                    password=str(d.get('password','')).strip() or secrets.token_urlsafe(10)
                    if len(username)<3 or len(display)<2 or role not in ROLES or len(password)<10:
                        self.error(400,'Nombre, usuario (mínimo 3), función y clave (mínimo 10) son obligatorios.');return
                    try:
                        db.execute('INSERT INTO users(username,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?)',(username,display,role,hash_pass(password),now()))
                        audit(db,actor,'usuario-creado',None,username+' · '+role)
                        db.commit();self.send_json(201,{'ok':True,'username':username,'password':password});return
                    except sqlite3.IntegrityError:
                        self.error(409,'El usuario ya existe.');return
                if path=='/api/me/password':
                    d=self.jsonbody()
                    old=str(d.get('current',''));new=str(d.get('password',''))
                    if not verify_pass(old,user['password_hash']):self.error(403,'La contraseña actual es incorrecta.');return
                    if len(new)<10:self.error(400,'Utiliza al menos 10 caracteres.');return
                    db.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_pass(new),user['id']))
                    db.execute('DELETE FROM sessions WHERE user_id=? AND token<>?',(user['id'],self.headers.get('Authorization','')[7:]))
                    audit(db,actor,'clave-cambiada')
                    db.commit();self.send_json(200,{'ok':True});return
                if path=='/api/tasks':
                    d=self.jsonbody()
                    title=str(d.get('title','')).strip()
                    typ=str(d.get('type','feature'))
                    try:
                        frustration=int(d.get('frustration'))
                        estimated=int(d.get('author_effort'))
                    except Exception: self.error(400,'Indica molestia y dificultad prevista de 1 a 10.');return
                    if not (3<=len(title)<=160 and typ in ('feature','fix') and 1<=frustration<=10 and 1<=estimated<=10):
                        self.error(400,'Revisa título, tipo y puntuaciones de 1 a 10.');return
                    tid='OX-'+uuid.uuid4().hex[:7].upper()
                    db.execute('''INSERT INTO tasks(id,type,title,description,why,acceptance,depends,chapter,phase,priority,owner,frustration,author_effort,created_by,updated_by,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                        tid,typ,title,str(d.get('description',''))[:12000],str(d.get('why',''))[:6000],str(d.get('acceptance',''))[:6000],str(d.get('depends',''))[:300],str(d.get('chapter',''))[:150],str(d.get('phase',''))[:150],str(d.get('priority','P1')) if d.get('priority') in ('P0','P1','P2') else 'P1',str(d.get('owner',''))[:90],frustration,estimated,actor,actor,now(),now()))
                    audit(db,actor,'tarea-creada',tid,typ+': '+title)
                    db.commit()
                    self.send_json(201,{'task':self.task_detail(db,tid)});return
                if path.startswith('/api/tasks/') and path.endswith('/comments'):
                    tid=path.split('/')[3]
                    if not db.execute('SELECT 1 FROM tasks WHERE id=?',(tid,)).fetchone():self.error(404,'Tarea no encontrada.');return
                    d=self.jsonbody();body=str(d.get('body','')).strip()
                    if not body or len(body)>5000:self.error(400,'La respuesta debe tener entre 1 y 5000 caracteres.');return
                    db.execute('INSERT INTO comments(id,task_id,author,body,created_at) VALUES(?,?,?,?,?)',(uuid.uuid4().hex,tid,actor,body,now()))
                    audit(db,actor,'comentario',tid,body[:160])
                    db.commit();self.send_json(201,{'task':self.task_detail(db,tid)});return
                if path.startswith('/api/tasks/') and path.endswith('/files'):
                    tid=path.split('/')[3]
                    if not db.execute('SELECT 1 FROM tasks WHERE id=?',(tid,)).fetchone():self.error(404,'Tarea no encontrada.');return
                    raw=self.getbody();ctype=self.headers.get('Content-Type','')
                    if 'multipart/form-data' not in ctype or 'boundary=' not in ctype:self.error(400,'Se esperaba un adjunto de formulario.');return
                    parsed=BytesParser(policy=default).parsebytes(('Content-Type: '+ctype+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
                    parts=[x for x in parsed.iter_parts() if x.get_filename()]
                    if len(parts)!=1:self.error(400,'Sube un archivo por solicitud.');return
                    part=parts[0];orig=Path(part.get_filename()).name[:180]
                    ext=Path(orig).suffix.lower()
                    if ext not in ALLOWED_EXT:self.error(400,'Extensión no admitida. Utiliza documentos, imágenes, ZIP o archivos técnicos.');return
                    payload=part.get_payload(decode=True)
                    if not payload or len(payload)>MAX_FILE:self.error(400,'Archivo vacío o superior a 15 MB.');return
                    saved=uuid.uuid4().hex+ext
                    f=FILES/saved;f.write_bytes(payload)
                    mime=(part.get_content_type() or 'application/octet-stream')[:90]
                    fid=uuid.uuid4().hex
                    db.execute('INSERT INTO attachments(id,task_id,original_name,storage_name,mime,size,uploaded_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(fid,tid,orig,saved,mime,len(payload),actor,now()))
                    audit(db,actor,'adjunto-subido',tid,orig)
                    db.commit();self.send_json(201,{'attachment':{'id':fid,'name':orig},'task':self.task_detail(db,tid)});return
                if path.startswith('/api/tasks/') and path.endswith('/transition'):
                    tid=path.split('/')[3]
                    task=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
                    if not task:self.error(404,'Tarea no encontrada.');return
                    d=self.jsonbody();target=str(d.get('status',''))
                    allowed={'open':{'review'},'review':{'open','history'},'history':{'open'}}
                    if target not in allowed.get(task['status'],set()):self.error(400,'Transición no válida.');return
                    if target=='history' and user['role'] not in ('admin','revision'):
                        self.error(403,'La validación final requiere función de revisión o dirección.');return
                    if target=='history' and not str(task['acceptance']).strip():
                        self.error(400,'Para aprobar, especifica cómo comprobar el resultado.');return
                    version=d.get('version')
                    if version!=task['version']:self.error(409,'Alguien modificó esta tarea. Actualiza antes de continuar.',current=self.task_detail(db,tid));return
                    action={'review':'enviado-a-revision','open':'devuelto-a-trabajo','history':'revision-aprobada'}[target]
                    db.execute('''UPDATE tasks SET status=?,version=version+1,updated_at=?,updated_by=?,reviewed_by=?,reviewed_at=? WHERE id=?''',(
                        target,now(),actor,actor if target=='history' else None,now() if target=='history' else None,tid))
                    audit(db,actor,action,tid,'De '+task['status']+' a '+target)
                    db.commit();self.send_json(200,{'task':self.task_detail(db,tid)});return
                self.error(404,'Operación desconocida.');return
        except ValueError as e:self.error(400,str(e))
        except Exception as e:
            print('ERROR POST',repr(e),file=sys.stderr)
            self.error(500,'No se pudo completar la operación. Revisa la consola del servidor.')

    def do_PUT(self):
        path=urlsplit(self.path).path
        if not path.startswith('/api/tasks/') or path.count('/')!=3:self.error(404,'No encontrado.');return
        tid=path.split('/')[3]
        try:
            d=self.jsonbody()
            with LOCK,connection() as db:
                user=self.require(db)
                if not user:return
                task=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
                if not task:self.error(404,'Tarea no encontrada.');return
                if d.get('version')!=task['version']:
                    self.error(409,'La tarea ha cambiado en otro equipo. Copia tus cambios y actualiza la ficha.',current=self.task_detail(db,tid));return
                fields=['type','title','description','why','acceptance','depends','chapter','phase','priority','owner','frustration','author_effort','dev_effort','dev_response']
                values={}
                for f in fields:
                    val=d.get(f,task[f])
                    if f in ('frustration','author_effort','dev_effort'):
                        if val is None or val=='':val=None
                        else:
                            try: val=int(val)
                            except: raise ValueError('Las puntuaciones deben ser números de 1 a 10.')
                            if val<1 or val>10:raise ValueError('Las puntuaciones deben estar entre 1 y 10.')
                    else:
                        val=str(val)
                    values[f]=val
                if values['type'] not in ('feature','fix') or len(values['title'].strip())<3 or len(values['title'])>160 or values['priority'] not in ('P0','P1','P2'):
                    raise ValueError('Revisa el tipo, la prioridad y el título.')
                if len(values['description'])>12000 or len(values['acceptance'])>6000 or len(values['why'])>6000:
                    raise ValueError('Uno de los textos es demasiado largo.')
                actor=user['display_name']
                db.execute('UPDATE tasks SET '+','.join(f+'=?' for f in fields)+', version=version+1,updated_at=?,updated_by=? WHERE id=?', [values[f] for f in fields]+[now(),actor,tid])
                changed=[f for f in fields if values[f]!=task[f]]
                audit(db,actor,'tarea-editada',tid,', '.join(changed))
                db.commit();self.send_json(200,{'task':self.task_detail(db,tid)});return
        except ValueError as e:self.error(400,str(e))
        except Exception as e:
            print('ERROR PUT',repr(e),file=sys.stderr)
            self.error(500,'No se pudo guardar la tarea. Revisa la consola del servidor.')


def main():
    ap=argparse.ArgumentParser(description='OxEye · Lista de trabajo compartida')
    ap.add_argument('--host',default='127.0.0.1',help='0.0.0.0 permite acceso desde otros equipos de la red local')
    ap.add_argument('--port',type=int,default=8765)
    args=ap.parse_args()
    initialize()
    srv=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'\n  OxEye · Tareas compartidas: http://127.0.0.1:{args.port}')
    if args.host=='0.0.0.0':
        print('  Acceso en la misma red: http://IP_DE_ESTE_ORDENADOR:'+str(args.port))
        print('  No expongas este puerto directamente a Internet. Para acceso remoto utiliza HTTPS y un servidor protegido.')
    print('  Los datos compartidos se guardan en:',DATA)
    print('  Para detenerlo: Ctrl+C\n',flush=True)
    try:srv.serve_forever()
    except KeyboardInterrupt: print('\nCerrando servidor...')
    finally:srv.server_close()

if __name__=='__main__': main()
