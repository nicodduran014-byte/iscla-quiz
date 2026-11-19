/* Controladores de pantalla. El almacenamiento queda detrás de window.ISCLA. */
(() => {
  const db = window.ISCLA;
  const page = document.body.dataset.page;
  const params = new URLSearchParams(location.search);
  const byId = id => document.getElementById(id);
  const select = (query, parent = document) => parent.querySelector(query);
  const all = (query, parent = document) => [...parent.querySelectorAll(query)];
  const set = (id, value) => { byId(id).textContent = value; };
  const show = (id, visible = true) => { byId(id).hidden = !visible; };
  const listen = (id, event, fn) => byId(id).addEventListener(event, fn);
  const el = (tag, cls = '', value) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (value !== undefined) node.textContent = value;
    return node;
  };
  const button = (label, cls) => Object.assign(el('button', 'btn ' + cls, label), {type:'button'});
  const link = (label, href, cls = '') => Object.assign(el('a', cls, label), { href });
  const url = (name, query = {}) => {
    const str = new URLSearchParams(query).toString();
    return name + '.html' + (str ? '?' + str : '');
  };
  const go = (page, query, replace = false) => {
    if (replace) location.replace(url(page, query));
    else location.assign(url(page, query));
  };
  const qty = (n, s, p) => n + ' ' + (n === 1 ? s : p);
  const text = error => error instanceof DOMException
    ? 'El navegador no pudo guardar tu sesión. Habilitá el almacenamiento del sitio y volvé a intentar.'
    : error.message || 'No pudimos completar la acción.';
  function message(id, content = '', error = false) {
    const node = byId(id);
    node.textContent = content; node.hidden = !content;
    node.classList.toggle('error', error && Boolean(content));
  }
  function clear(form, msg) {
    all('[aria-invalid]', form).forEach(node => node.removeAttribute('aria-invalid'));
    message(msg);
  }
  function errorIn(form, msg, error) {
    message(msg, text(error), true);
    if (error.field) {
      const field = form.querySelector('[name="' + error.field + '"]');
      if (field) { field.setAttribute('aria-invalid', 'true'); field.focus(); }
    }
  }
  async function copyValue(value, msg, field = null) {
    try {
      if (navigator.clipboard) await navigator.clipboard.writeText(value);
      else {
        let temp = null;
        const input = field || (temp = el('textarea','sr-only'));
        if (temp) { input.value = value; document.body.append(input); }
        input.focus(); input.select();
        try { if (!document.execCommand('copy')) throw new Error(); }
        finally { temp?.remove(); }
      }
      message(msg,field ? 'Enlace copiado.' : 'Código copiado.');
    } catch {
      if (field) { field.focus(); field.select(); }
      message(msg, field ? 'Seleccioná y copiá el enlace.' : 'Seleccioná el código y copialo a mano.');
    }
  }
  function inviteControls() {
    listen('show-qr','click',() => {
      const dialog = byId('qr-dialog');
      byId('qr-large').src = byId('join-qr').src;
      const code = new URL(byId('invite-link').value).searchParams.get('codigo') || '';
      set('qr-large-code',code); dialog.showModal();
    });
    listen('copy-invite','click',() => {
      const field = byId('invite-link');
      if (field.value) copyValue(field.value,'invite-message',field);
    });
  }
  function renderInvite(room,visible) {
    show('room-invite',Boolean(visible && room.joinUrl && room.qrPath));
    if (!visible || !room.joinUrl || !room.qrPath) return;
    const field = byId('invite-link');
    if (field.value !== room.joinUrl) {
      field.value = room.joinUrl;
      byId('join-qr').src = room.qrPath;
      message('invite-message');
    }
  }
  async function busy(node, action) {
    if (node.disabled) return;
    node.disabled = true;
    try { await action(); }
    finally { node.disabled = false; }
  }
  const letters = 'ABCD';
  const FEEDBACK_MS = 7000;
  function codeFromUrl() { return db.normalizeCode(params.get('codigo')); }

  function home() {
    const phrases = [
      ['El conocimiento es tu poder,', 'el desafío es superarte'],
      ['Innovación y pensamiento crítico,', 'el compromiso es tu futuro'],
      ['Aprendé jugando y en equipo,', 'superá tus propios límites'],
    ];
    all('[data-slide]').forEach(tab => tab.addEventListener('click', () => {
      if (tab.getAttribute('aria-pressed') === 'true') return;
      const [one, two] = phrases[Number(tab.dataset.slide)];
      const motto = byId('motto');
      motto.classList.remove('motto-enter');
      motto.replaceChildren(document.createTextNode(one), el('br'), document.createTextNode(two));
      // Read only after the text changes, so a new click restarts the short transition.
      if (window.matchMedia?.('(prefers-reduced-motion: no-preference)').matches) {
        void motto.offsetWidth;
        motto.classList.add('motto-enter');
      }
      all('[data-slide]').forEach(item => item.setAttribute('aria-pressed', String(item === tab)));
    }));
  }

  function join() {
    const form = byId('join-form');
    byId('codigo').value = codeFromUrl();
    listen('codigo', 'input', () => { byId('codigo').removeAttribute('aria-invalid'); });
    listen('alias', 'input', () => { byId('alias').removeAttribute('aria-invalid'); });
    form.addEventListener('submit', e => {
      e.preventDefault(); clear(form, 'join-message');
      const data = new FormData(form);
      busy(select('[type=submit]', form), async () => {
        try {
          const room = await db.joinRoom(data.get('codigo'), data.get('alias'));
          go('sala', { codigo: room.code });
        } catch (error) { errorIn(form, 'join-message', error); }
      });
    });
  }

  function teacher() {
    const registration = params.get('registro') === '1';
    const form = byId(registration ? 'register-form' : 'teacher-form');
    const msg = registration ? 'register-message' : 'teacher-message';
    show('teacher-form',!registration);
    show('register-form',registration);
    if (registration) {
      document.title = 'Crear cuenta docente | ISCLA QUIZ';
      set('teacher-title','Creá tu cuenta docente');
      set('teacher-intro','Registrate con tu correo y el código que te dio la institución.');
      byId('tab-ingresar').removeAttribute('aria-current');
      byId('tab-registro').setAttribute('aria-current','page');
    }
    function invalid(field,msg) { return Object.assign(new Error(msg),{field}); }
    form.addEventListener('submit',e => {
      e.preventDefault(); clear(form,msg);
      const data = Object.fromEntries(new FormData(form));
      const email = form.elements.correo;
      busy(select('[type=submit]',form),async () => {
        try {
          if (registration && !data.nombre.trim()) throw invalid('nombre','Ingresá tu nombre y apellido.');
          if (!email.checkValidity()) throw invalid('correo','Ingresá un correo electrónico válido.');
          if (!data.clave) throw invalid('clave','Ingresá tu contraseña.');
          if (registration) {
            if (data.clave.length < 8 || !data.clave.trim()) throw invalid('clave','Usá una contraseña de al menos 8 caracteres.');
            if (data.clave !== data.confirmacion) throw invalid('confirmacion','Las contraseñas no coinciden.');
            if (!data.codigo.trim()) throw invalid('codigo','Ingresá el código de registro docente.');
            await db.registerTeacher(data);
          } else {
            await db.openTeacher(data.correo,data.clave);
          }
          form.reset(); go('admin',{vista:'inicio'});
        } catch(error) {
          if (!registration && error.status === 401) form.elements.clave.value = '';
          errorIn(form,msg,error);
        }
      });
    });
    form.addEventListener('input',() => clear(form,msg));
  }

  async function allowPanel(nav) {
    const teacher = await db.getTeacher();
    if (!teacher) { go('docente',{},true); return false; }
    try { await db.loadPanel(); }
    catch (error) { if (error.status === 401) { go('docente',{},true); return false; } throw error; }
    select('[data-nav="' + nav + '"]')?.setAttribute('aria-current','page');
    set('teacher-name',teacher.nombre); show('teacher-name');
    listen('logout','click',() => busy(byId('logout'),async () => {
      try { await db.closeTeacher(); go('inicio',{},true); }
      catch (error) { message('panel-auth-message',text(error),true); }
    }));
    show('contenido');
    window.addEventListener('pageshow',e => {
      if (!e.persisted) return;
      db.getTeacher().then(active => { if (!active) go('docente',{},true); }).catch(() => {});
    });
    return true;
  }

  async function dashboard() {
    const valid = ['inicio', 'preguntas', 'cuestionarios', 'resultados'];
    const view = valid.includes(params.get('vista')) ? params.get('vista') : 'preguntas';
    if (!(await allowPanel(view))) return;
    select('[data-view="' + view + '"]').hidden = false;
    const quizForm = byId('quiz-form'), questionForm = byId('question-form');
    const quizDialog = byId('quiz-dialog'), questionDialog = byId('question-dialog'), confirmDialog = byId('confirm-dialog');
    let quizEdit = null, questionEdit = null, deleteTarget = null, toastTimer, pageIndex = 0;
    const perPage = 10;
    function toast(value) {
      set('panel-status', value); show('panel-status');
      clearTimeout(toastTimer); toastTimer = setTimeout(() => show('panel-status', false), 4000);
    }
    all('[data-close]').forEach(item => item.addEventListener('click', () => item.closest('dialog').close()));
    function replaceSelect(node, quizzes, firstLabel) {
      const selected = node.value;
      node.replaceChildren(new Option(firstLabel, ''), ...quizzes.map(quiz => new Option(quiz.titulo, quiz.id)));
      if (quizzes.some(q => q.id === selected)) node.value = selected;
    }
    function fillQuizzes() {
      const quizzes = db.listQuizzes();
      replaceSelect(byId('question-filter'), quizzes, 'Todos');
      replaceSelect(questionForm.elements.quiz, quizzes, 'Seleccioná uno');
    }
    function openQuiz(quiz) {
      quizEdit = quiz || null; quizForm.reset(); clear(quizForm, 'quiz-message');
      set('quiz-dialog-title', quiz ? 'Editar cuestionario' : 'Nuevo cuestionario');
      if (quiz) ['titulo','materia','autor'].forEach(k => { quizForm.elements[k].value = quiz[k]; });
      quizDialog.showModal(); quizForm.elements.titulo.focus();
    }
    function openQuestion(q, quizId) {
      const quizzes = db.listQuizzes();
      if (!quizzes.length) { toast('Creá un cuestionario antes de agregar preguntas.'); return; }
      questionEdit = q ? { id:q.id, origin:quizId } : null;
      questionForm.reset(); clear(questionForm, 'question-message'); fillQuizzes();
      questionForm.elements.quiz.value = quizId || byId('question-filter').value || (quizzes.length === 1 ? quizzes[0].id : '');
      if (q) {
        questionForm.elements.tema.value = q.tema;
        questionForm.elements.texto.value = q.texto;
        if (questionForm.elements.explicacion) questionForm.elements.explicacion.value = q.explicacion || '';
        questionForm.elements.correcta.value = String(q.correcta);
        q.opciones.forEach((choice, i) => { questionForm.elements['op' + letters[i]].value = choice; });
      }
      set('question-dialog-title', q ? 'Editar pregunta' : 'Nueva pregunta');
      questionDialog.showModal();
      (questionForm.elements.quiz.value ? questionForm.elements.texto : questionForm.elements.quiz).focus();
    }
    function renderQuestions() {
      const qs = db.listQuizzes();
      const raw = qs.flatMap(quiz => quiz.preguntas.map(q => ({quiz, q})));
      const term = byId('question-search').value.trim().toLocaleLowerCase('es-AR');
      const selected = byId('question-filter').value;
      const filtered = raw.filter(({quiz,q}) => (!selected || quiz.id === selected)
        && (!term || [q.texto, q.tema, quiz.materia, quiz.titulo].some(v => v.toLocaleLowerCase('es-AR').includes(term))));
      const lastPage = Math.max(0,Math.ceil(filtered.length/perPage)-1);
      pageIndex = Math.min(pageIndex,lastPage);
      const offset = pageIndex*perPage;
      byId('bank-prev').disabled = pageIndex === 0;
      byId('bank-next').disabled = pageIndex >= lastPage;
      const rows = filtered.slice(offset,offset+perPage).map(({quiz,q}, i) => {
        const tr = el('tr');
        const question = el('td', 'question-name'); question.append(el('b', '', q.texto), el('small', '', quiz.titulo));
        const subject = el('td', 'question-subject', quiz.materia);
        if (q.tema) subject.append(el('small', '', q.tema));
        const status = el('td'); status.append(el('span', 'tag soft', 'Lista'));
        const actions = el('td', 'question-actions'), wrap = el('div', 'row-actions');
        const edit = button('Editar', 'small navy'), remove = button('Eliminar', 'small delete-link');
        edit.setAttribute('aria-label', 'Editar pregunta: ' + q.texto);
        remove.setAttribute('aria-label', 'Eliminar pregunta: ' + q.texto);
        edit.addEventListener('click', () => openQuestion(q, quiz.id));
        remove.addEventListener('click', () => {
          deleteTarget = { id:q.id, quiz:quiz.id }; confirmDialog.showModal();
          select('.btn.ghost', confirmDialog).focus();
        });
        wrap.append(edit, remove); actions.append(wrap);
        tr.append(el('td', 'question-number', offset + i + 1), question, subject, el('td', 'question-type', 'Opción múltiple'), status, actions);
        return tr;
      });
      if (!rows.length) {
        const cell = el('td', 'row-empty', 'No hay preguntas que coincidan con los filtros.');
        cell.colSpan = 6; const row = el('tr'); row.append(cell); rows.push(row);
      }
      byId('question-rows').replaceChildren(...rows);
      set('question-count', filtered.length ? 'Mostrando ' + (offset+1) + '–' + Math.min(offset+perPage,filtered.length) + ' de ' + filtered.length : '0 resultados');
      byId('question-summary').replaceChildren(...[[raw.length,'Preguntas'],[qs.length,'Cuestionarios']].map(([n,l]) => {
        const box = el('div'); box.append(el('b','',n),el('small','',l)); return box;
      }));
    }
    function renderQuizzes() {
      const cards = db.listQuizzes().map(quiz => {
        const card = el('article','inner quick-card');
        const edit = button('Editar cuestionario','soft');
        const add = button('Agregar pregunta','ghost');
        edit.addEventListener('click', () => openQuiz(quiz)); add.addEventListener('click', () => openQuestion(null, quiz.id));
        card.append(el('span','eyebrow',quiz.materia), el('h2','',quiz.titulo), el('p','',quiz.autor),
          el('span','tag soft',qty(quiz.preguntas.length,'pregunta','preguntas')),edit,add);
        return card;
      });
      byId('quiz-list').replaceChildren(...cards);
    }
    function renderHistory() {
      const rooms = db.listRooms();
      const rows = rooms.map(room => {
        const row = el('article','history-row'), description = el('div');
        const state = {waiting:'En espera',playing:'En curso',finished:'Terminada'}[room.status];
        description.append(el('b','',room.quiz.titulo),el('p','','Código ' + room.code + ' · ' + state + ' · ' + qty(room.count,'jugador','jugadores')));
        const target = room.status !== 'finished'
          ? link('Volver a la sala',url('sala',{codigo:room.code,rol:'docente'}),'btn soft small')
          : link('Ver ranking',url('ranking',{codigo:room.code,origen:'panel'}),'btn soft small');
        row.append(description,target); return row;
      });
      byId('history-list').replaceChildren(...(rows.length ? rows : [el('p','padded muted','Todavía no hay partidas creadas.')]));
    }
    function renderOverview() {
      const qs = db.listQuizzes(), rooms = db.listRooms();
      const cards = [
        [qs.length,'Cuestionarios','cuestionarios'], [qs.reduce((n,q) => n + q.preguntas.length,0),'Preguntas','preguntas'],
        [rooms.filter(r => r.status === 'finished').length,'Partidas terminadas','resultados'],
      ];
      byId('quick-grid').classList.add('quick-stats');
      byId('quick-grid').replaceChildren(...cards.map(([n,label,href]) => {
        const card = link('', url('admin',{vista:href}), 'inner quick-card quick-link');
        card.append(el('strong','tag soft',n),el('h2','',label)); return card;
      }));
    }
    function render() {
      fillQuizzes();
      if (view === 'preguntas') renderQuestions();
      if (view === 'cuestionarios') renderQuizzes();
      if (view === 'resultados') renderHistory();
      if (view === 'inicio') renderOverview();
    }
    listen('new-quiz','click',() => openQuiz());
    listen('new-question','click',() => openQuestion());
    listen('question-filter','change',() => { pageIndex=0; renderQuestions(); });
    listen('question-search','input',() => { pageIndex=0; renderQuestions(); });
    listen('bank-prev','click',() => { pageIndex=Math.max(0,pageIndex-1); renderQuestions(); });
    listen('bank-next','click',() => { pageIndex++; renderQuestions(); });
    quizForm.addEventListener('submit', e => {
      e.preventDefault(); clear(quizForm, 'quiz-message');
      busy(select('[type=submit]',quizForm), async () => {
        try {
          await db.saveQuiz(Object.fromEntries(new FormData(quizForm)), quizEdit?.id);
          quizDialog.close(); render(); toast('Cuestionario guardado.');
        } catch (error) { errorIn(quizForm,'quiz-message',error); }
      });
    });
    questionForm.addEventListener('submit', e => {
      e.preventDefault(); clear(questionForm,'question-message');
      const data = new FormData(questionForm);
      busy(select('[type=submit]',questionForm), async () => {
        try {
          const val = data.get('correcta');
          const explanation = data.has('explicacion') ? {explicacion:data.get('explicacion')} : {};
          await db.saveQuestion(data.get('quiz'), { texto:data.get('texto'),tema:data.get('tema'),...explanation,
            opciones:[...letters].map(l => data.get('op'+l)), correcta:val === null ? -1 : Number(val) }, questionEdit?.id, questionEdit?.origin);
          questionDialog.close(); render(); toast('Pregunta guardada.');
        } catch (error) { errorIn(questionForm,'question-message',error); }
      });
    });
    listen('confirm-form','submit',e => {
      e.preventDefault();
      busy(select('[type=submit]',e.currentTarget), async () => {
        try { await db.deleteQuestion(deleteTarget.quiz,deleteTarget.id); confirmDialog.close(); render(); toast('Pregunta eliminada.'); }
        catch (error) { confirmDialog.close(); toast(text(error)); }
      });
    });
    render();
    window.addEventListener('pageshow',e => {
      if (e.persisted && !quizDialog.open && !questionDialog.open && !confirmDialog.open) {
        db.loadPanel().then(render).catch(error => toast(text(error)));
      }
    });
  }

  async function newRoom() {
    if (!(await allowPanel('partida'))) return;
    const form = byId('room-form'), dropdown = byId('select-quiz'), count = byId('select-count');
    let active = null;
    const quizzes = db.listQuizzes();
    dropdown.replaceChildren(new Option('Seleccioná un cuestionario',''), ...quizzes.map(quiz => {
      const option = new Option(quiz.titulo + ' · ' + qty(quiz.preguntas.length,'pregunta','preguntas'),quiz.id);
      option.disabled = quiz.preguntas.length === 0;
      return option;
    }));
    dropdown.options[0].disabled = true;
    function syncCount() {
      const max = quizzes.find(q => q.id === dropdown.value)?.preguntas.length || 0;
      count.disabled = max === 0;
      count.replaceChildren(...(max ? Array.from({length:max},(_,i) => new Option(
        max === i+1 ? 'Todas (' + max + ')' : String(i+1),String(i+1)
      )) : [new Option('Elegí un cuestionario primero','')]));
      if (max) count.value = String(max);
    }
    syncCount();
    listen('select-quiz','change',() => { clear(form,'room-message'); syncCount(); });
    if (quizzes.every(quiz => !quiz.preguntas.length)) message('room-message','Agregá preguntas a un cuestionario antes de crear una partida.');

    inviteControls();
    function render(room) {
      active = room;
      set('created-code',room.code);
      set('created-hint',room.quiz.titulo + ' · ' + qty(room.quiz.preguntas.length,'pregunta','preguntas'));
      byId('host-room').href = url('sala',{codigo:room.code,rol:'docente'});
      byId('student-room').href = room.joinUrl;
      renderInvite(room,true);
      message('copy-message'); show('created-actions');
    }
    listen('copy-created','click',() => { if (active) copyValue(active.code,'copy-message'); });
    form.addEventListener('submit',e => {
      e.preventDefault(); clear(form,'room-message');
      busy(select('[type=submit]',form),async () => {
        try {
          if (!dropdown.value) throw Object.assign(new Error('Elegí un cuestionario.'),{field:'quiz'});
          render(await db.createRoom(dropdown.value,Number(count.value)));
          byId('created-title').scrollIntoView({block:'nearest'});
        } catch (error) { errorIn(form,'room-message',error); }
      });
    });
  }

  async function waitingRoom() {
    const code = codeFromUrl(), host = params.get('rol') === 'docente';
    let leaving = false, lastState = '', lastPlayers = '', stop = () => {};
    function fallback(msg) {
      show('room-content',false); set('room-fallback-text',msg); show('room-fallback');
    }
    function render(room) {
      message('room-connection');
      if (!room) { fallback('Para entrar a esta sala, ingresá con el código de la partida y tu alias.'); return; }
      if (room.me && room.status !== 'waiting' && !host) {
        stop(); go(room.status === 'finished' ? 'ranking' : 'jugar',{codigo:code},true); return;
      }
      show('room-fallback',false); show('room-content');
      const playing = room.status === 'playing';
      const waiting = room.status === 'waiting';
      const change = lastState !== room.status;
      if (change) {
        lastState = room.status;
        set('room-code',room.code);
        set('room-state',waiting ? 'Esperando que el docente inicie…' : playing ? 'Partida en curso' : 'Partida terminada');
        set('room-desc',waiting ? 'La primera pregunta aparecerá cuando el docente inicie la partida.' :
          playing ? 'Los estudiantes ya están respondiendo. Podés seguir el ranking en vivo.' : 'Ya podés consultar la clasificación final.');
        renderInvite(room,host && waiting);
        show('host-controls', host);
        show('start-game',host && waiting);
        show('close-room',host && playing);
        show('live-ranking',host && !waiting);
        byId('live-ranking').href = url('ranking',{codigo:code,origen:'panel'});
        set('join-room-title',host ? 'Partida de ' + room.quiz.titulo : 'Ya estás en la sala');
        set('join-room-hint',host ? qty(room.quiz.preguntas.length,'pregunta','preguntas') : 'Mantené abierta esta pantalla para jugar.');
        const me = room.players.find(p => p.id === room.me);
        show('joined-user',Boolean(me));
        if (me) set('joined-name',me.name);
      }
      const snapshot = JSON.stringify(room.players.map(p => [p.id,p.name]));
      if (snapshot !== lastPlayers) {
        lastPlayers = snapshot;
        set('player-count',room.players.length);
        byId('player-list').replaceChildren(...room.players.map(p =>
          el('li',p.id === room.me ? 'is-self' : '',p.name + (p.id === room.me ? ' (vos)' : ''))
        ));
        show('no-players',room.players.length === 0);
      }
    }
    listen('hourglass','click',() => {
      const hour=byId('hourglass');
      if (!hour.classList.contains('spin')) {
        hour.classList.add('spin'); setTimeout(() => hour.classList.remove('spin'),760);
      }
    });
    inviteControls();
    listen('copy-room','click',() => copyValue(code,'copy-message'));
    listen('start-game','click',() => busy(byId('start-game'),async () => {
      try { const room = await db.startRoom(code); message('start-message'); render(room); byId('live-ranking').focus(); }
      catch (error) { message('start-message',text(error),true); }
    }));
    const closeDialog=byId('finish-dialog');
    listen('close-room','click',() => { closeDialog.returnValue=''; closeDialog.showModal(); });
    closeDialog.addEventListener('close',() => {
      if (closeDialog.returnValue !== 'finish') return;
      busy(byId('close-room'),async () => {
        try { render(await db.closeRoom(code)); byId('live-ranking').focus(); }
        catch(error) { message('start-message',text(error),true); }
      });
    });
    if (host) {
      byId('leave-room').href = url('admin',{vista:'resultados'});
      byId('leave-room').lastChild.textContent = ' Volver al panel';
    } else listen('leave-room','click', e => {
      if (leaving) { e.preventDefault(); return; }
      e.preventDefault(); leaving = true;
      db.leaveRoom(code).then(() => { stop(); go('inicio',{},true); }).catch(error => {
        leaving=false; message('room-connection',text(error),true);
      });
    });
    function connection(error) {
      if (host && error.status === 401) { go('docente',{},true); return; }
      if (byId('room-content').hidden) fallback(text(error));
      else message('room-connection',text(error),true);
    }
    try { render(await db.getRoom(code,host)); } catch (error) { connection(error); }
    stop=db.watchRoom(code,host,render,connection);
  }

  async function gameContext() {
    const code = codeFromUrl(), room = await db.getRoom(code);
    const fallback = msg => { set('game-fallback-text', msg); show('game-fallback'); };
    if (!room) { fallback('No hay una partida disponible en esta sesión. Volvé a ingresar con tu alias.'); return; }
    const player = room.players.find(p => p.id === room.me);
    if (!player) { fallback('Primero ingresá a la partida como estudiante en esta pestaña.'); return; }
    if (room.status === 'waiting') { go('sala',{codigo:code},true); return; }
    return {code,room,player,answers:room.answers};
  }
  async function question() {
    const context = await gameContext();
    if (!context) return;
    const {code,room,player,answers} = context, questions = room.quiz.preguntas;
    if (room.status === 'finished' || answers.length >= questions.length) { go('ranking',{codigo:code},true); return; }
    const asked = params.get('pregunta');
    const index = asked === null ? answers.length : Number(asked);
    if (!Number.isInteger(index) || index < 0 || index > answers.length) { go('jugar',{codigo:code},true); return; }
    if (index < answers.length) { go('resultado',{codigo:code,pregunta:index},true); return; }
    function redirectResolved(latest) {
      if (latest?.answers[index]) { go('resultado',{codigo:code,pregunta:index},true); return true; }
      if (latest?.status === 'finished') { go('ranking',{codigo:code},true); return true; }
      return false;
    }
    let clock;
    try { clock = await db.openQuestion(code,index); }
    catch (error) {
      if (error.status === 409 && redirectResolved(await db.getRoom(code).catch(() => null))) return;
      throw error;
    }
    const deadline = performance.now() + clock.remainingMs, wallDeadline = Date.now() + clock.remainingMs;
    const q = clock.question, form = byId('answer-form'), progress = byId('progress-bar');
    progress.max = questions.length; progress.value = index + 1;
    set('game-progress','Pregunta ' + (index + 1) + ' de ' + questions.length);
    set('game-matter', q.tema || room.quiz.materia);
    set('game-score',player.score + ' pts'); set('game-quiz',room.quiz.titulo); set('game-question',q.texto);
    byId('play-options').replaceChildren(...q.opciones.map((label,i) => {
      const outer = el('label','choice');
      const input = Object.assign(el('input'),{type:'radio',name:'respuesta',value:String(i)});
      outer.append(input,el('span','choice-letter',letters[i]),el('span','',label));
      return outer;
    }));
    const clockBar = byId('clock-bar'), clockSeconds = byId('clock-seconds');
    clockBar.max = clock.durationMs;
    const remaining = () => Math.max(0,Math.min(deadline - performance.now(),wallDeadline - Date.now()));
    const fieldset = select('fieldset',form), confirm = byId('confirm-answer'), skip = byId('skip-question');
    let sending = false, done = false, expired = false, ticker, stop = () => {};
    function cleanup() {
      done = true; clearInterval(ticker); stop();
      document.removeEventListener('visibilitychange',tick);
    }
    function markExpired() {
      expired = true; clearInterval(ticker);
      byId('question-clock').classList.add('urgent');
      clockBar.value = 0; clockSeconds.textContent = '0 s';
      show('confirm-answer',false); show('skip-question',false);
      fieldset.disabled = true;
    }
    function tick() {
      if (done || expired) return;
      const ms = remaining(), secs = Math.ceil(ms / 1000), label = secs + ' s';
      if (clockSeconds.textContent !== label) clockSeconds.textContent = label;
      clockBar.value = ms;
      byId('question-clock').classList.toggle('urgent',secs <= 3);
      if (ms === 0) {
        markExpired();
        if (!sending) send(null);
      }
    }
    async function send(value) {
      if (sending || done) return;
      if (!expired && remaining() === 0) markExpired();
      if (expired) value = null;
      sending = true;
      fieldset.disabled = confirm.disabled = skip.disabled = true;
      show('retry-timeout',false);
      if (expired) message('answer-message','Se terminó el tiempo. Registrando la pregunta sin responder…');
      try {
        await db.submitAnswer(code,index,value);
        cleanup();
        go('resultado',{codigo:code,pregunta:index},true);
      } catch (error) {
        if (redirectResolved(await db.getRoom(code).catch(() => null))) { cleanup(); return; }
        sending = false;
        if (expired || remaining() === 0) {
          markExpired(); show('retry-timeout');
        } else {
          fieldset.disabled = confirm.disabled = skip.disabled = false;
        }
        message('answer-message',text(error),true);
      }
    }
    form.addEventListener('change',() => message('answer-message'));
    form.addEventListener('submit',e => {
      e.preventDefault();
      if (sending || done || expired) return;
      const value = new FormData(form).get('respuesta');
      if (value === null) {
        message('answer-message','Elegí una opción antes de confirmar.',true);
        select('input[name="respuesta"]',form).focus(); return;
      }
      send(Number(value));
    });
    listen('skip-question','click',() => send(null));
    listen('retry-timeout','click',() => send(null));
    stop = db.watchRoom(code,false,latest => {
      if (!sending && redirectResolved(latest)) cleanup();
    });
    show('question-play');
    document.addEventListener('visibilitychange',tick);
    ticker = setInterval(tick,120);
    tick();
  }
  async function result() {
    const context = await gameContext();
    if (!context) return;
    const {code,room,player,answers} = context, questions = room.quiz.preguntas;
    const asked = params.get('pregunta');
    const index = asked === null ? answers.length - 1 : Number(asked), answer = answers[index], q = questions[index];
    if (!Number.isInteger(index) || index < 0 || !q || !answer) { go('jugar',{codigo:code},true); return; }
    const skipped = answer.selected === null, good = answer.points === 100;
    const status = good ? 'Correcta' : answer.timed_out ? 'Tiempo agotado' : skipped ? 'Sin respuesta' : 'Incorrecta';
    set('result-progress','Pregunta ' + (index + 1) + ' de ' + questions.length);
    set('result-score','Total de la partida · ' + player.score + ' pts');
    byId('outcome').classList.toggle('good',good);
    byId('outcome').classList.toggle('bad',!good && !skipped);
    if (!good) select('#outcome .outcome-icon').textContent = skipped ? '—' : '×';
    set('outcome-title',status); set('outcome-points','+' + answer.points + ' pts');
    set('outcome-msg',good ? 'Sumaste 100 puntos en esta pregunta.' : answer.timed_out
      ? 'Se terminó el tiempo. La pregunta quedó sin responder.'
      : skipped ? 'Pasaste sin elegir una opción.' : 'Esta pregunta no suma puntos.');
    set('result-question',q.texto);
    byId('answer-detail').replaceChildren(
      el('dt','','Tu respuesta'), el('dd','',skipped ? 'No elegiste una opción.' : letters[answer.selected] + ' · ' + q.opciones[answer.selected]),
      el('dt','','Opción correcta'),el('dd','',letters[q.correcta] + ' · ' + q.opciones[q.correcta])
    );
    if (q.explicacion && byId('answer-explanation')) {
      set('answer-explanation-text',q.explicacion);
      show('answer-explanation');
    }
    const showRanking = room.status === 'finished' || answers.length >= questions.length;
    const clockBar = byId('feedback-clock-bar'), clockSeconds = byId('feedback-clock-seconds');
    set('next-question-label',showRanking ? 'Ver ranking' : 'Continuar');
    set('feedback-clock-label',showRanking ? 'Ranking en' : 'Siguiente pregunta en');
    clockBar.max = FEEDBACK_MS;
    let remaining = FEEDBACK_MS, visibleSince = null, advanced = false, ticker;
    function advance() {
      if (advanced) return;
      advanced = true;
      clearInterval(ticker);
      document.removeEventListener('visibilitychange',syncVisibility);
      go(showRanking ? 'ranking' : 'jugar', {codigo:code},true);
    }
    function tick() {
      if (advanced) return;
      const elapsed = visibleSince === null ? 0 : performance.now() - visibleSince;
      const ms = Math.max(0,remaining - elapsed);
      const label = Math.ceil(ms / 1000) + ' s';
      if (clockSeconds.textContent !== label) clockSeconds.textContent = label;
      clockBar.value = ms;
      if (ms === 0 && !document.hidden) advance();
    }
    function syncVisibility() {
      if (advanced) return;
      if (document.hidden) {
        if (visibleSince !== null) remaining = Math.max(0,remaining - (performance.now() - visibleSince));
        visibleSince = null;
      } else if (visibleSince === null) visibleSince = performance.now();
      tick();
    }
    listen('next-question','click',advance);
    show('answer-result');
    document.addEventListener('visibilitychange',syncVisibility);
    ticker = setInterval(tick,120);
    syncVisibility();
  }
  async function ranking() {
    const code = codeFromUrl(), panelView = params.get('origen') === 'panel';
    let rankingSnapshot = '', stop = () => {};
    if (panelView && !(await db.getTeacher())) { go('docente',{},true); return; }
    function render(room) {
      message('ranking-connection');
      const id = room?.me;
      if (room && !panelView && room.status === 'waiting') { go('sala',{codigo:code},true); return; }
      if (!room || (!panelView && !room.players.some(p => p.id === id))) {
        set('game-fallback-text', 'Ingresá a la partida para consultar su clasificación.');
        show('ranking-content',false); show('game-fallback'); return;
      }
      show('game-fallback',false);
      const final = room.status === 'finished';
      set('ranking-title', final ? 'Ranking final' : 'Ranking provisional');
      set('ranking-quiz',room.quiz.titulo + ' · Código ' + code);
      const count = room.players.filter(p => p.answered >= room.quiz.preguntas.length).length;
      const description = final ? qty(room.players.length,'participante','participantes') :
        count + ' de ' + room.players.length + ' ya terminaron. La clasificación se actualiza en vivo.';
      if (byId('ranking-status').textContent !== description) set('ranking-status',description);
      if (final) stop();
      const sorted = [...room.players].sort((a,b) => b.score-a.score || a.name.localeCompare(b.name,'es-AR'));
      const located = sorted.map((p,i) => ({p,pos:i > 0 && sorted[i-1].score === p.score
        ? sorted.findIndex(prev => prev.score === p.score) + 1 : i + 1}));
      if (panelView) {
        byId('ranking-back').href = url('admin',{vista:'resultados'}); byId('ranking-back').lastChild.textContent = ' Volver a resultados';
      }
      show('ranking-content');
      const snapshot = JSON.stringify(located.map(({p,pos}) => [p.id,p.name,p.score,pos]));
      if (rankingSnapshot === snapshot) return;
      rankingSnapshot = snapshot;
      const top = located.slice(0,3);
      const order = top.length === 3 ? [1,0,2] : top.length === 2 ? [1,0] : top.length === 1 ? [0] : [];
      const podium = order.map(i => {
        const {p,pos} = top[i], card = el('div','podium-col');
        card.dataset.pos = String(pos);
        card.dataset.medal = String(i + 1);
        card.append(el('span','avatar-initial',[...p.name][0].toLocaleUpperCase('es-AR')),
          el('span','podium-name',p.name),
          el('span','podium-score',p.score+' pts'),el('span','podium-step',pos+'°'));
        return card;
      });
      byId('podium').replaceChildren(...podium); show('podium',podium.length > 0);
      byId('ranking-rows').replaceChildren(...located.map(({p,pos}) => {
        const row = el('tr',p.id === id ? 'is-me' : ''), position = el('td'), name = el('td');
        const badge = el('span','rank-position',pos+'°');
        badge.dataset.place = String(pos);
        position.append(badge);
        const identity = el('span','rank-caption-name');
        identity.append(el('span','',p.name));
        if (p.id === id) identity.append(el('span','rank-self','(vos)'));
        name.append(identity);
        row.append(position,name,el('td','',p.score+' pts')); return row;
      }));
      show('ranking-empty', sorted.length === 0);
    }
    function connection(error) {
      if (panelView && error.status === 401) { go('docente',{},true); return; }
      if (byId('ranking-content').hidden) {
        set('game-fallback-text',text(error)); show('game-fallback');
      } else message('ranking-connection',text(error),true);
    }
    try {
      const room = await db.getRoom(code,panelView);
      render(room);
      if (room?.status === 'finished') return;
    } catch(error) { connection(error); }
    stop=db.watchRoom(code,panelView,render,connection);
  }
  const pages = { inicio:home, acceso:join, docente:teacher, admin:dashboard, partida:newRoom, sala:waitingRoom, jugar:question, resultado:result, ranking };
  Promise.resolve().then(() => pages[page]?.()).catch(error => {
    const content = byId('contenido');
    const box = el('section','inner padded fallback');
    box.append(el('h1','','No pudimos abrir esta pantalla'),el('p','',text(error)),link('Volver al inicio','inicio.html','btn primary'));
    content.replaceChildren(box); content.hidden = false;
    console.warn('ISCLA QUIZ · No se pudo iniciar la pantalla.',error);
  });
})();
