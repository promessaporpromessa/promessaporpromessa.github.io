/*
 * Promessa por Promessa — camada de dados do site.
 * Reproduz a pequena API que a página usa (dash.data, dash.calc, dash.onData, dash.setLink)
 * lendo os arquivos JSON da pasta /data. As tarefas de atualização só precisam trocar esses JSON.
 */
(function () {
  const store = {};
  const calcs = {};
  const subs = [];
  let version = 0;
  const memo = {};
  let pending = false;

  const fire = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; version += 1; subs.forEach((f) => { try { f(); } catch (e) { console.error(e); } }); });
  };

  const bust = () => `?v=${Math.floor(Date.now() / 600000)}`; // renova o cache a cada 10 min

  let ver = bust();
  function load(id) {
    store[id] = { status: 'loading' };
    fetch(`data/${id}.json${ver}`, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((d) => { store[id] = { status: 'ok', data: Array.isArray(d) ? d : (d.rows || []) }; fire(); })
      .catch(() => { store[id] = { status: 'error' }; fire(); });
  }

  window.dash = {
    data(id) {
      const c = calcs[id];
      if (c) {
        if (memo[id] && memo[id].v === version) return memo[id].r;
        const ins = c.inputs.map((i) => store[i]);
        let r;
        if (ins.some((x) => !x || x.status === 'error')) r = ins.some((x) => x && x.status === 'error') ? { status: 'error' } : { status: 'loading' };
        else if (ins.some((x) => x.status !== 'ok')) r = { status: 'loading' };
        else { try { r = { status: 'ok', data: c.fn(...ins.map((x) => x.data)) }; } catch (e) { console.error(e); r = { status: 'error' }; } }
        memo[id] = { v: version, r };
        return r;
      }
      return store[id] || { status: 'loading' };
    },
    calc(id, opts) { calcs[id] = opts; },
    onData(f) { subs.push(f); },
    setLink(name) { try { history.replaceState(null, '', name === 'visao' ? location.pathname + location.search : `#${name}`); } catch (e) { /* ignore */ } },
  };

  fetch(`data/index.json?t=${Date.now()}`, { cache: 'no-store' })
    .then((r) => r.json())
    .then((idx) => {
      if (idx.atualizado) ver = `?v=${encodeURIComponent(idx.atualizado)}`;
      (idx.datasets || []).forEach(load);
      const el = document.querySelector('.ob-site-upd');
      if (el && idx.atualizado) {
        const d = new Date(idx.atualizado);
        el.textContent = `Dados atualizados em ${d.toLocaleDateString('pt-BR')} às ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
      }
    })
    .catch(() => { console.error('Não foi possível carregar data/index.json'); });
})();
