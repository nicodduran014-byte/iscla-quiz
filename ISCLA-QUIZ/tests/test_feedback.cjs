const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');

const js = readFileSync(join(__dirname,'../static/js/juego.js'),'utf8');
const question = { texto:'¿Cuál es correcta?', opciones:['Una','Dos','Tres','Cuatro'], correcta:1,
  explicacion:'Ejemplo de una devolución breve.' };

async function setup({ final = false, timedOut = false, hidden = false } = {}) {
  const nodes = new Map(), listeners = new Map(), navigations = [];
  let now = 0, tick;
  const make = () => ({ hidden:true, textContent:'', classList:{toggle() {}},
    replaceChildren() {}, addEventListener(type,callback) { this[type] = callback; } });
  function element(id) {
    if (!nodes.has(id)) nodes.set(id,make());
    return nodes.get(id);
  }
  const document = { hidden, body:{dataset:{page:'resultado'}}, createElement:make,
    getElementById:element, querySelector:element,
    addEventListener:(type,callback) => listeners.set(type,callback),
    removeEventListener:type => listeners.delete(type) };
  const room = { status:'playing', me:'jugador', players:[{id:'jugador',score:100}],
    quiz:{preguntas:final ? [question] : [question,null]},
    answers:[timedOut ? {selected:null,points:0,timed_out:true} : {selected:1,points:100}] };
  runInNewContext(js,{
    document, URLSearchParams, DOMException, console,
    location:{search:'?codigo=AB12CD&pregunta=0',replace:url => navigations.push(url)},
    window:{ISCLA:{normalizeCode:code => code,getRoom:async () => room}},
    performance:{now:() => now}, setInterval:callback => { tick = callback; return 1; },
    clearInterval:() => { tick = null; },
  });
  await new Promise(resolve => setImmediate(resolve));
  return { element,navigations,tickAt:ms => { now = ms; tick?.(); },
    visibilityAt(ms,hidden) { now = ms; document.hidden = hidden; listeners.get('visibilitychange')?.(); } };
}

test('la devolución aparece 7 segundos y avanza una sola vez',async () => {
  const s = await setup();
  assert.equal(s.element('answer-result').hidden,false);
  assert.equal(s.element('answer-explanation').hidden,false);
  assert.equal(s.element('answer-explanation-text').textContent,question.explicacion);
  assert.equal(s.element('feedback-clock-seconds').textContent,'7 s');
  s.tickAt(6999);
  assert.equal(s.element('feedback-clock-seconds').textContent,'1 s');
  assert.deepEqual(s.navigations,[]);
  s.tickAt(7000);
  s.element('next-question').click();
  assert.deepEqual(s.navigations,['jugar.html?codigo=AB12CD']);
});

test('la última respuesta omitida muestra la devolución y lleva al ranking',async () => {
  const s = await setup({final:true,timedOut:true});
  assert.equal(s.element('feedback-clock-label').textContent,'Ranking en');
  assert.equal(s.element('outcome-title').textContent,'Tiempo agotado');
  s.tickAt(7000);
  assert.deepEqual(s.navigations,['ranking.html?codigo=AB12CD']);
});

test('la pestaña oculta no consume tiempo de lectura',async () => {
  const s = await setup({hidden:true});
  s.tickAt(15_000);
  assert.equal(s.element('feedback-clock-seconds').textContent,'7 s');
  s.visibilityAt(15_000,false);
  s.visibilityAt(17_000,true);
  s.tickAt(30_000);
  assert.equal(s.element('feedback-clock-seconds').textContent,'5 s');
  assert.deepEqual(s.navigations,[]);
  s.visibilityAt(30_000,false);
  s.tickAt(35_000);
  assert.deepEqual(s.navigations,['jugar.html?codigo=AB12CD']);
});

test('Continuar permite avanzar antes y cancela el salto automático',async () => {
  const s = await setup();
  s.element('next-question').click();
  s.tickAt(7000);
  assert.deepEqual(s.navigations,['jugar.html?codigo=AB12CD']);
});
