/* El servidor es la autoridad de las salas, las respuestas y los puntajes. */
(() => {
  const normalizeCode = raw => String(raw ?? '').trim().replace(/\s+/g, '').toUpperCase();
  const base = code => '/api/partidas/' + encodeURIComponent(code);
  const key = code => 'iscla:participante:' + code;
  let panel = {quizzes:[],rooms:[]};

  async function request(path, options = {}) {
    const headers = {};
    if (options.body) {
      headers['X-ISCLA-Request'] = '1';
      headers['Content-Type'] = 'application/json';
    }
    if (options.code) {
      const token = sessionStorage.getItem(key(options.code));
      if (token) headers['X-ISCLA-Student'] = token;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(path, {
        method:options.body ? 'POST' : 'GET', credentials:'same-origin', cache:'no-store',
        headers, body:options.body ? JSON.stringify(options.body) : undefined, signal:controller.signal
      });
      if (response.headers.get('Content-Type')?.includes('application/json')) {
        const data = await response.json();
        if (response.ok) return data;
        throw Object.assign(new Error(data.message || 'No se pudo completar la solicitud.'),{status:response.status,field:data.field});
      }
      throw new Error('No encontramos el servidor de ISCLA QUIZ. Verificá la dirección o iniciá el servidor de la aplicación.');
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError) {
        throw new Error('No pudimos conectar con ISCLA QUIZ. Revisá tu conexión y volvé a intentar.');
      }
      throw error;
    } finally { clearTimeout(timeout); }
  }

  async function getRoom(code, host = false) {
    if (!/^[A-Z0-9]{6}$/.test(code)) return null;
    try { return await request(base(code) + (host ? '/docente' : ''), {code:host ? undefined : code}); }
    catch (error) {
      if (error.status === 404 || (error.status === 403 && !host)) return null;
      throw error;
    }
  }
  async function loadPanel() { panel = await request('/api/panel'); return panel; }
  async function update(path, body) {
    await request(path,{body}); await loadPanel();
  }
  function watchRoom(code, host, onRoom, onError) {
    let timer, stopped = false, pending = false;
    async function poll() {
      if (stopped || pending) return;
      pending = true;
      try {
        const room = await getRoom(code,host);
        if (!stopped) onRoom(room);
      } catch (error) { if (!stopped) onError?.(error); }
      finally {
        pending = false;
        if (!stopped) timer = setTimeout(poll,document.hidden ? 3500 : 1400);
      }
    }
    function resume(e) {
      if ((e.type === 'visibilitychange' && document.hidden) || stopped) return;
      clearTimeout(timer); poll();
    }
    timer = setTimeout(poll,1400);
    document.addEventListener('visibilitychange',resume);
    window.addEventListener('pageshow',resume);
    return () => {
      stopped = true; clearTimeout(timer);
      document.removeEventListener('visibilitychange',resume);
      window.removeEventListener('pageshow',resume);
    };
  }

  window.ISCLA = Object.freeze({
    normalizeCode,
    getTeacher: async () => (await request('/api/session')).docente || null,
    openTeacher: (correo,clave) => request('/api/login',{body:{correo,clave}}),
    registerTeacher: body => request('/api/registro',{body}),
    closeTeacher: () => request('/api/logout',{body:{}}),
    loadPanel, listQuizzes: () => panel.quizzes, listRooms: () => panel.rooms,
    saveQuiz: (data,id) => update('/api/cuestionarios',{...data,id}),
    saveQuestion: (quiz,input,id,origen) => update('/api/preguntas',{...input,quiz,id,origen}),
    deleteQuestion: (quiz,id) => update('/api/preguntas/eliminar',{quiz,id}),
    createRoom: (quiz,cantidad) => request('/api/partidas',{body:{quiz,cantidad}}),
    joinRoom: async (codigo,alias) => {
      const code = normalizeCode(codigo);
      const room = await request('/api/unirse',{code,body:{codigo:code,alias}});
      sessionStorage.setItem(key(room.code),room.token);
      return room;
    },
    startRoom: code => request(base(code)+'/iniciar',{body:{}}),
    closeRoom: code => request(base(code)+'/cerrar',{body:{}}),
    leaveRoom: async code => {
      await request(base(code)+'/salir',{code,body:{}});
      sessionStorage.removeItem(key(code));
    },
    openQuestion: (code,pregunta) => request(base(code)+'/pregunta',{code,body:{pregunta}}),
    submitAnswer: (code,pregunta,opcion) => request(base(code)+'/responder',{code,body:{pregunta,opcion}}),
    getRoom, watchRoom,
  });
})();
