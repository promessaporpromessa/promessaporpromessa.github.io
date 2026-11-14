/*
 * Promessa por Promessa — arquivo de notícias.
 * A lista abre com os últimos 15 dias (dataset "noticias"). Os meses mais antigos ficam em
 * datasets mensais ("noticias_AAAA_MM", listados em "noticias_arquivo") e só são baixados
 * quando alguém escolhe um mês ou "Todo o histórico" no seletor de período.
 */
(function () {
  const st = { per: '', nw: null, sel: null, sig: '' };
  const MES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
  const rotulo = (m) => `${MES[Number(m.slice(5, 7)) - 1]} de ${m.slice(0, 4)}`;

  function arquivo() {
    const r = dash.data('noticias_arquivo');
    return r.status === 'ok' ? r.data : [];
  }

  function seletor(base) {
    const root = document.getElementById('card-noticias');
    if (!root) return;
    if (!st.sel) {
      const tema = root.querySelector('.ob-nw-tema');
      if (!tema) return;
      const s = document.createElement('select');
      s.className = 'ob-in ob-nw-per';
      s.setAttribute('aria-label', 'Período');
      s.dataset.source = 'noticias_arquivo';
      s.addEventListener('change', () => {
        st.per = s.value;
        if (st.nw) { st.nw.dia = ''; st.nw.all = false; }
        if (window.nwDraw) window.nwDraw();
      });
      tema.before(s);
      st.sel = s;
    }
    const arq = arquivo();
    const meses = [...new Set([...arq.map((a) => a.mes), ...base.map((n) => String(n.data).slice(0, 7))])].sort().reverse();
    const sig = meses.join('|');
    if (sig === st.sig) return;
    st.sig = sig;
    st.sel.replaceChildren(
      new Option('Últimos 15 dias', ''),
      ...meses.map((m) => new Option(rotulo(m)[0].toUpperCase() + rotulo(m).slice(1), m)),
      ...(arq.length ? [new Option('Todo o histórico', 'tudo')] : []),
    );
    st.sel.value = st.per;
  }

  window.NWA = {
    rows(nw) {
      st.nw = nw;
      const base = dash.data('noticias');
      if (base.status !== 'ok') return base;
      seletor(base.data);
      if (!st.per) return base;
      const arq = arquivo();
      const ids = (st.per === 'tudo' ? arq : arq.filter((a) => a.mes === st.per)).map((a) => a.id);
      const list = document.querySelector('#card-noticias .ob-nw-list');
      if (list) list.dataset.source = ['noticias', ...ids].join(' ');
      const parts = ids.map((id) => dash.data(id));
      if (parts.some((p) => p.status === 'error')) return { status: 'error' };
      if (parts.some((p) => p.status !== 'ok')) return { status: 'loading' };
      const seen = new Set();
      const out = [];
      [base, ...parts].forEach((p) => p.data.forEach((n) => {
        if (seen.has(n.id)) return;
        if (st.per !== 'tudo' && String(n.data).slice(0, 7) !== st.per) return;
        seen.add(n.id); out.push(n);
      }));
      return { status: 'ok', data: out };
    },
    ecoEv(id) {
      return arquivo().some((a) => String(a.eco_eventos || '').split(',').includes(id));
    },
  };
})();
