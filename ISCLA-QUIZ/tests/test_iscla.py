from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from http.cookiejar import CookieJar
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPCookieProcessor
from xml.etree import ElementTree
import json
import sqlite3
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'servidor'))
from app import App, ROOT, Store


class Client:
    def __init__(self,origin):
        self.origin=origin
        self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
        self.token=''

    def req(self,path,data=None,spec=None):
        headers={}
        if self.token:
            headers['X-ISCLA-Student']=self.token
        if data is not None:
            headers.update({'Content-Type':'application/json','X-ISCLA-Request':'1'})
        headers.update(spec or {})
        req=Request(self.origin+path, data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            result=self.opener.open(req,timeout=5)
        except HTTPError as e:
            result=e
        with result:
            raw=result.read()
            return result.code,(json.loads(raw) if result.headers.get_content_type()=='application/json' else raw)


TEACHER = dict(nombre='Lucía Prueba',correo='lucia@example.test',clave='Clave-docente-1',
               confirmacion='Clave-docente-1',codigo='Invitacion-2026')


class QuizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/'quiz.sqlite3'
        with sqlite3.connect(cls.path) as pre:
            pre.execute('CREATE TABLE sessions (token TEXT PRIMARY KEY, until INTEGER NOT NULL)')
            pre.execute('INSERT INTO sessions VALUES (?,?)',('sesion-anterior',9999999999))
            pre.execute('CREATE TABLE quizzes (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            pre.execute('''CREATE TABLE answers (player TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                n INTEGER NOT NULL, selected INTEGER, points INTEGER NOT NULL, PRIMARY KEY(player,n))''')
            pre.execute('INSERT INTO quizzes VALUES (?,?)',
                        ('legacy',json.dumps(dict(id='legacy',titulo='Cuestionario existente',preguntas=[]))))
        cls.server=App(('127.0.0.1',0),cls.path,TEACHER['codigo'],'https://quiz.example.test')
        # El proveedor HTTPS delegaría TLS a un proxy. En este test el cliente usa HTTP local.
        cls.server.https=False
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.origin=f'http://127.0.0.1:{cls.server.server_port}'
        result=Client(cls.origin).req('/api/registro',TEACHER)
        assert result[0]==201,result

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)
        cls.tmp.cleanup()

    def teacher(self):
        t=Client(self.origin)
        auth={'correo':TEACHER['correo'],'clave':TEACHER['clave']}
        self.assertEqual(t.req('/api/login',auth),(200,{'teacher':True,'docente':{'nombre':TEACHER['nombre']}}))
        return t

    def test_bank_and_editor(self):
        d=self.teacher()
        bank=d.req('/api/panel')[1]['quizzes']
        self.assertEqual([q['titulo'] for q in bank if q['id'] in ('so','ada','pi')],
            ['Sistemas Operativos','Análisis y Diseño de Aplicaciones','Proyectos Informáticos'])
        for q in bank:
            if q['id'] not in ('so','ada','pi'): continue
            self.assertEqual(len(q['preguntas']),12)
            for question in q['preguntas']:
                self.assertEqual(len(set(question['opciones'])),4)
                self.assertIn(question['correcta'],range(4))
        created=d.req('/api/cuestionarios',{'titulo':'Prueba QA','autor':'Docente','materia':'Tecnología'})[1]
        quiz_id=created['id']
        q=dict(quiz=quiz_id,texto='¿Pregunta?',tema='Pregunta',opciones=['Uno','Dos','Tres','Cuatro'],correcta=0)
        self.assertEqual(d.req('/api/preguntas',q)[0],200)
        copied=next(i for i in d.req('/api/panel')[1]['quizzes'] if i['id']==quiz_id)['preguntas'][0]
        self.assertEqual(d.req('/api/preguntas',{**q,'id':copied['id'],'correcta':3})[0],200)
        _,room=d.req('/api/partidas',{'quiz':quiz_id,'cantidad':1})
        self.assertEqual(d.req('/api/preguntas/eliminar',{'quiz':quiz_id,'id':copied['id']})[0],200)
        self.assertEqual(len(Store(self.path).room(room['code'],True)['quiz']['preguntas']),1)

    def test_access_separation(self):
        visitor=Client(self.origin)
        self.assertEqual(visitor.req('/api/panel')[0],401)
        self.assertEqual(visitor.req('/api/login',{'correo':TEACHER['correo'],'clave':'incorrecta'})[0],401)
        self.assertEqual(visitor.req('/api/login',{'clave':TEACHER['codigo']})[0],401)
        self.assertEqual(visitor.req('/api/login',{'clave':TEACHER['clave']},{'X-ISCLA-Request':'0'})[0],403)
        d=self.teacher()
        self.assertEqual(d.req('/api/logout',{})[1],{'teacher':False})
        self.assertEqual(d.req('/api/panel')[0],401)
        self.assertEqual(visitor.req('/servidor/preguntas.json')[0],404)
        self.assertEqual(visitor.req('/datos/iscla.sqlite3')[0],404)
        self.assertEqual(visitor.req('/static/js/datos-demo.js')[0],404)
        for p in (ROOT/'templates').glob('*.html'):
            status, body=visitor.req('/templates/'+p.name)
            self.assertEqual(status,200,p.name)
            self.assertIn(b'js/servicio.js',body,p.name)
            self.assertNotIn(b'flow-steps',body,p.name)
            self.assertNotIn(b'demo',body.lower(),p.name)

    def test_docente_registration_and_persistence(self):
        second=Client(self.origin)
        account={**TEACHER,'nombre':'María Profesora','correo':'marIA@Example.Test','clave':'Otra-clave-97','confirmacion':'Otra-clave-97'}
        self.assertEqual(second.req('/api/registro',{**account,'correo':'no-es-correo'})[0],400)
        self.assertEqual(second.req('/api/registro',{**account,'confirmacion':'distinta'})[0],400)
        self.assertEqual(second.req('/api/registro',{**account,'codigo':'No-es-la-invitacion'})[0],403)
        self.assertEqual(second.req('/api/session'),(200,{'teacher':False}))
        self.assertEqual(second.req('/api/registro',account),(201,{'teacher':True,'docente':{'nombre':account['nombre']}}))
        self.assertIn('legacy',{q['id'] for q in second.req('/api/panel')[1]['quizzes']})
        duplicate=Client(self.origin)
        self.assertEqual(duplicate.req('/api/registro',{**account,'correo':'MARIA@example.test'})[0],409)
        self.assertEqual(duplicate.req('/api/panel')[0],401)
        first=self.teacher()
        self.assertEqual(first.req('/api/session')[1]['docente']['nombre'],TEACHER['nombre'])
        second.req('/api/logout',{})
        self.assertEqual(second.req('/api/panel')[0],401)
        self.assertEqual(first.req('/api/panel')[0],200)
        independent=Client(self.origin)
        self.assertEqual(independent.req('/api/login',{'correo':' maria@example.test ','clave':account['clave']})[0],200)
        self.assertEqual(independent.req('/api/session')[1]['docente']['nombre'],account['nombre'])
        saved=Store(self.path).teacher_by_email('maria@example.test')
        self.assertEqual(saved['email'],'maria@example.test')
        self.assertEqual(len(saved['salt']),16)
        self.assertEqual(len(saved['digest']),32)
        self.assertNotEqual(saved['digest'],account['clave'].encode())
        same=Client(self.origin)
        self.assertEqual(same.req('/api/registro',{**account,'nombre':'Otra Profesora','correo':'segundo@example.test'})[0],201)
        same_key=Store(self.path).teacher_by_email('segundo@example.test')
        self.assertNotEqual(same_key['digest'],saved['digest'])

    def test_real_round_with_two_separate_clients_and_qr(self):
        d=self.teacher()
        status,room=d.req('/api/partidas',{'quiz':'so','cantidad':3})
        self.assertEqual(status,201)
        code=room['code']
        prefix='/api/partidas/'+code
        invitation=urlsplit(room['joinUrl'])
        self.assertEqual((invitation.scheme,invitation.netloc),('https','quiz.example.test'))
        self.assertEqual(invitation.path,'/templates/acceso.html')
        self.assertEqual(parse_qs(invitation.query),{'codigo':[code]})
        st,qr=d.req(room['qrPath'])
        self.assertEqual(st,200)
        self.assertTrue(ElementTree.fromstring(qr).tag.endswith('svg'))
        a,b=Client(self.origin),Client(self.origin)
        self.assertEqual(a.req(room['qrPath'])[0],401)
        self.assertEqual(a.req(prefix+'/iniciar',{})[0],401)
        self.assertEqual(d.req(prefix+'/iniciar',{})[0],409)
        for c,name in [(a,'Sofía'),(b,'Mateo')]:
            status,js=c.req('/api/unirse',{'codigo':code,'alias':name})
            self.assertEqual(status,200)
            c.token=js['token']
        self.assertNotEqual(a.token,b.token)
        self.assertEqual(Client(self.origin).req('/api/unirse',{'codigo':code,'alias':'sofía'})[0],409)
        self.assertEqual(a.req(prefix)[1]['quiz']['preguntas'],[None]*3)
        self.assertEqual(d.req(prefix+'/iniciar',{})[1]['status'],'playing')
        self.assertEqual(Client(self.origin).req('/api/unirse',{'codigo':code,'alias':'Tarde'})[0],409)
        self.assertEqual(a.req(prefix)[1]['quiz']['preguntas'],[None]*3)
        _,opened=a.req(prefix+'/pregunta',{'pregunta':0})
        self.assertNotIn('correcta',opened['question'])
        self.assertEqual(a.req(prefix+'/responder',{'pregunta':1,'opcion':3})[0],409)
        def answer(client,n,selected):
            client.req(prefix+'/pregunta',dict(pregunta=n))
            return client.req(prefix+'/responder',dict(pregunta=n,opcion=selected))
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(answer,c,0,1) for c in (a,b)]
            self.assertEqual([f.result()[1]['points'] for f in futures],[100,100])
        self.assertEqual(answer(a,0,0)[1],{'selected':1,'points':100})
        self.assertEqual(a.req(prefix)[1]['quiz']['preguntas'][0]['correcta'],1)
        self.assertIsNone(b.req(prefix)[1]['quiz']['preguntas'][1])
        self.assertEqual(answer(a,1,0)[1]['points'],0)
        self.assertEqual(answer(a,2,None)[1]['points'],0)
        self.assertEqual(a.req(prefix)[1]['status'],'playing')
        self.assertEqual(answer(b,1,3)[1]['points'],100)
        self.assertEqual(answer(b,2,0)[1]['points'],100)
        final=d.req(prefix+'/docente')[1]
        self.assertEqual(final['status'],'finished')
        self.assertEqual(sorted((r['name'],r['score']) for r in final['players']),[('Mateo',300),('Sofía',100)])
        self.assertEqual(Store(self.path).room(code,True)['status'],'finished')

    def test_manual_close_preserves_scores(self):
        d=self.teacher()
        c=Client(self.origin)
        _,r=d.req('/api/partidas',{'quiz':'pi','cantidad':5})
        code=r['code']; path='/api/partidas/'+code
        c.token=c.req('/api/unirse',{'codigo':code,'alias':'Ana'})[1]['token']
        d.req(path+'/iniciar',{})
        c.req(path+'/pregunta',{'pregunta':0})
        c.req(path+'/responder',{'pregunta':0,'opcion':3})
        self.assertEqual(d.req(path+'/cerrar',{})[1]['status'],'finished')
        self.assertEqual(c.req(path+'/responder',{'pregunta':1,'opcion':0})[0],409)
        self.assertEqual(len(c.req(path)[1]['answers']),1)

    def test_fifteen_second_clock_is_per_player_and_per_question(self):
        d=self.teacher()
        _,room=d.req('/api/partidas',{'quiz':'so','cantidad':2})
        code=room['code']; path='/api/partidas/'+code
        a,b=Client(self.origin),Client(self.origin)
        for client,alias in ((a,'Reloj A'),(b,'Reloj B')):
            client.token=client.req('/api/unirse',{'codigo':code,'alias':alias})[1]['token']
        def open_q(client,n):
            return client.req(path+'/pregunta',{'pregunta':n})
        def answer(client,n,selected):
            return client.req(path+'/responder',{'pregunta':n,'opcion':selected})
        epoch=1_700_000_000_000
        with patch('app.now_ms',return_value=epoch) as clock:
            self.assertEqual(open_q(a,0)[0],409)
            d.req(path+'/iniciar',{})
            self.assertEqual(answer(a,0,1)[0],409)
            self.assertEqual(open_q(a,1)[0],409)
            status,data=open_q(a,0)
            self.assertEqual((status,data['durationMs'],data['remainingMs']),(200,15000,15000))
            self.assertNotIn('correcta',data['question'])
            clock.return_value=epoch+6000
            self.assertEqual(open_q(a,0)[1]['remainingMs'],9000)
            self.assertEqual(open_q(b,0)[1]['remainingMs'],15000)
            clock.return_value=epoch+15000
            self.assertEqual(open_q(a,0)[1]['remainingMs'],0)
            timeout={'points':0,'selected':None,'timed_out':True}
            self.assertEqual(answer(a,0,1),(200,timeout))  # Correcta, pero ya vencida.
            self.assertEqual(answer(b,0,1),(200,{'points':100,'selected':1}))
            self.assertEqual(answer(a,0,None),(200,timeout))
            self.assertEqual(a.req(path)[1]['answers'],[timeout])
            self.assertEqual(a.req(path)[1]['quiz']['preguntas'][0]['correcta'],1)
            self.assertIsNone(a.req(path)[1]['quiz']['preguntas'][1])
            clock.return_value=epoch+40_000  # La devolución no consume tiempo de la pregunta siguiente.
            self.assertEqual(open_q(a,1)[1]['remainingMs'],15000)
            self.assertEqual(open_q(b,1)[1]['remainingMs'],15000)
            clock.return_value=epoch+54_999
            self.assertEqual(answer(a,1,3),(200,{'points':100,'selected':3}))
            clock.return_value=epoch+55_000
            self.assertEqual(answer(b,1,None),(200,timeout))
            self.assertEqual(d.req(path+'/docente')[1]['status'],'finished')

    def test_entire_cultura_general_round_and_feedback(self):
        d = self.teacher()
        bank = d.req('/api/panel')[1]['quizzes']
        culture = next(quiz for quiz in bank if quiz['id'] == 'cultura_general')
        self.assertEqual(culture['titulo'], 'Cultura general')
        questions = culture['preguntas']
        self.assertEqual(len(questions), 20)
        self.assertEqual({q['tema']:sum(1 for x in questions if x['tema']==q['tema']) for q in questions},
                         {'Películas':7,'Música':3,'Videojuegos':3,'Comidas y su origen':2,'Fútbol':2,'Astrología':3})
        self.assertTrue(all('Yo, robot' in q['texto'] for q in questions[:3]))
        self.assertEqual([q['correcta'] for q in questions],[1,3,2,0,2,1,3,0,2,3,1,0,2,3,0,1,0,3,1,2])
        self.assertEqual(len({q['id'] for q in questions}),20)
        status,room = d.req('/api/partidas',{'quiz':culture['id'],'cantidad':20})
        self.assertEqual(status,201)
        code = room['code']
        path = '/api/partidas/'+code
        player = Client(self.origin)
        player.token = player.req('/api/unirse',{'codigo':code,'alias':'Cultura QA'})[1]['token']
        d.req(path+'/iniciar',{})
        for i,q in enumerate(questions):
            self.assertEqual(len(set(q['opciones'])),4)
            status,opened = player.req(path+'/pregunta',{'pregunta':i})
            self.assertEqual(status,200)
            self.assertEqual(opened['durationMs'],15000)
            self.assertEqual(opened['question']['id'],q['id'])
            self.assertNotIn('correcta',opened['question'])
            self.assertNotIn('explicacion',opened['question'])
            self.assertEqual(player.req(path+'/responder',{'pregunta':i,'opcion':q['correcta']})[1]['points'],100)
            played = player.req(path)[1]['quiz']['preguntas']
            self.assertTrue(played[i]['explicacion'])
            self.assertEqual(played[i],q)
            self.assertEqual(played[i+1:],[None]*(19-i))
        final = d.req(path+'/docente')[1]
        self.assertEqual(final['status'],'finished')
        self.assertEqual(final['players'][0]['score'],2000)

    def test_updated_seed_preserves_existing_quiz(self):
        with TemporaryDirectory() as temp:
            db_path = Path(temp)/'existing.sqlite3'
            old_bank = Path(temp)/'old.json'
            old = {'id':'cultura','titulo':'Editado por mí','materia':'Cultura general','autor':'Docente','preguntas':[]}
            old_bank.write_text(json.dumps([old]),encoding='utf8')
            with patch('app.SEED',old_bank):
                Store(db_path)
            updated = Store(db_path)
            with updated.db() as db:
                self.assertEqual(updated.quiz(db,'cultura'),old)
                self.assertEqual(len(updated.quiz(db,'cultura_general')['preguntas']),20)

    def test_seed_refreshes_only_the_stock_quiz_and_keeps_room_snapshots(self):
        old = {'id':'cultura_general','titulo':'Cultura general','materia':'Cultura general','autor':'Equipo docente ISCLA',
               'preguntas':[{'id':'old','texto':'Pregunta de antes','tema':'Historial','opciones':['A','B','C','D'],'correcta':0}]}
        fingerprint = sha256(json.dumps(old,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        for is_custom in (False,True):
            with self.subTest(is_custom=is_custom), TemporaryDirectory() as temp:
                path = Path(temp)/'old.sqlite3'
                seed = Path(temp)/'test_old_seed.json'
                seed.write_text('[]',encoding='utf-8')
                with patch('app.SEED',seed):
                    prior = Store(path)
                prior.register_teacher('Profe','profe@example.test','Una-contraseña-larga')
                previous = dict(old,titulo='Mi cultura general') if is_custom else old
                with prior.db(True) as db:
                    db.execute('INSERT INTO quizzes VALUES(?,?)',(previous['id'],json.dumps(previous)))
                code = prior.new_room('cultura_general',1)['code']
                with patch('app.CULTURE_V1_HASH',fingerprint):
                    updated = Store(path)
                self.assertIsNotNone(updated.teacher_by_email('profe@example.test'))
                bank_id = 'cultura_general_desafio' if is_custom else 'cultura_general'
                with updated.db(True) as db:
                    quiz = updated.quiz(db,bank_id)
                    self.assertEqual(len(quiz['preguntas']),20)
                    self.assertEqual(json.loads(updated.room_row(db,code)['quiz']),previous)
                    if is_custom:
                        self.assertEqual(updated.quiz(db,'cultura_general'),previous)
                        self.assertEqual(quiz['titulo'],'Cultura general · Desafío')
                    else:
                        self.assertIsNone(updated.quiz(db,'cultura_general_desafio'))
                    quiz['titulo'] = 'Editada después de la actualización'
                    db.execute('UPDATE quizzes SET body=? WHERE id=?',(json.dumps(quiz),bank_id))
                restarted = Store(path)
                with restarted.db() as db:
                    self.assertEqual(restarted.quiz(db,bank_id),quiz)
                    if not is_custom:
                        self.assertIsNone(restarted.quiz(db,'cultura_general_desafio'))


if __name__=='__main__':
    unittest.main()
