#!/usr/bin/env python3
"""Recalcula data/atividade.json e data/atividade_listas.json com os dados abertos
da Câmara e do Senado (propostas como autor principal e coautor, leis, falas).

Uso:  python3 tools/atividade/atualizar.py  [pasta_de_trabalho]
Roda na raiz do repositório. Baixa uns 400 MB de CSV da Câmara na pasta de trabalho
(padrão /tmp/pp_atividade). tse_perfil.json e fotos.webp não mudam aqui.
mapa_ids.json liga o id do painel ao id da Câmara (camara) e ao código do Senado (senado).
"""
import csv, json, os, re, sys, subprocess, unicodedata, concurrent.futures as cf
from collections import Counter, defaultdict

R = os.getcwd()
T = os.path.dirname(os.path.abspath(__file__))
W = sys.argv[1] if len(sys.argv) > 1 else '/tmp/pp_atividade'
os.makedirs(W + '/sen', exist_ok=True)
csv.field_size_limit(10**9)
ANOS = (2023, 2024, 2025, 2026)
LEI = {'PL', 'PLP', 'PEC', 'PDL'}
m = json.load(open(T + '/mapa_ids.json'))

def curl(url, out=None, json_hdr=False):
    cmd = ['curl', '-sSL', '--retry', '3', '--max-time', '600' if out else '90']
    if json_hdr: cmd += ['-H', 'Accept: application/json']
    if out: cmd += ['-o', out]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    return r.stdout

# ---------- Câmara: CSV de proposições e autores ----------
for y in ANOS:
    for kind, pre in (('proposicoes', 'pr'), ('proposicoesAutores', 'pa')):
        f = f'{W}/{pre}{y}.csv'
        curl(f'https://dadosabertos.camara.leg.br/arquivos/{kind}/csv/{kind}-{y}.csv', f)
        if os.path.getsize(f) < 100000: sys.exit(f'download falhou: {kind}-{y}.csv')
cam2pid = {str(r['camara']): pid for pid, r in m.items() if 'camara' in r}
props = {}
for y in ANOS:
    with open(f'{W}/pr{y}.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f, delimiter=';'):
            dt = r['dataApresentacao'][:10]
            if dt < '2023-02-01': continue
            props[r['id']] = {'t': r['siglaTipo'], 'n': r['numero'], 'a': r['ano'], 'd': dt, 'e': (r['ementa'] or '').strip(),
                              's': r['ultimoStatus_descricaoSituacao'],
                              'u': f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={r['id']}"}
agg = defaultdict(lambda: {'princ': Counter(), 'co': Counter(), 'lp': 0, 'lc': 0, 'leis': [], 'ult': []})
seen = set()
for y in ANOS:
    with open(f'{W}/pa{y}.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f, delimiter=';'):
            dep = r['idDeputadoAutor']
            p = props.get(r['idProposicao'])
            if dep not in cam2pid or not p or (dep, r['idProposicao']) in seen: continue
            seen.add((dep, r['idProposicao']))
            a = agg[cam2pid[dep]]; princ = r['ordemAssinatura'] == '1'
            if princ:
                a['princ'][p['d'][:7]] += 1
                if p['t'] in LEI: a['lp'] += 1; a['ult'].append(p)
            else:
                a['co'][p['d'][:7]] += 1
                if p['t'] in LEI: a['lc'] += 1
            if p['s'] == 'Transformado em Norma Jurídica' and p['t'] in LEI:
                a['leis'].append(dict(p, papel='autor principal' if princ else 'coautor'))
cam = {pid: dict(a, casa_fonte='Câmara') for pid, a in agg.items()}
print('Câmara:', len(cam), 'deputados com propostas')

# ---------- Senado: processos por autor ----------
def nrm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z ]', '', s).strip()
names = {}
for u, k1, k2 in (('https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57', 'ListaParlamentarLegislatura', None),
                  ('https://legis.senado.leg.br/dadosabertos/senador/lista/atual', 'ListaParlamentarEmExercicio', None)):
    try:
        for s in json.loads(curl(u, json_hdr=True))[k1]['Parlamentares']['Parlamentar']:
            i = s['IdentificacaoParlamentar']; names[i['CodigoParlamentar']] = i['NomeParlamentar']
    except Exception as e:
        print('aviso: lista de senadores', u, e)
codes = sorted({r['senado'] for r in m.values() if 'senado' in r})
def get_sen(c):
    f = f'{W}/sen/{c}.json'
    try:
        d = json.loads(curl(f'https://legis.senado.leg.br/dadosabertos/processo?codigoParlamentarAutor={c}', json_hdr=True))
        json.dump(d, open(f, 'w'))
        return c, d
    except Exception:
        return c, None
with cf.ThreadPoolExecutor(6) as ex:
    SEN = dict(ex.map(get_sen, codes))
first_re = re.compile(r'^\s*Senador[a]?\s+(.+?)\s*\(')
sen = {}
for pid, r in m.items():
    if 'senado' not in r or not SEN.get(r['senado']): continue
    nm = nrm(names.get(r['senado'], ''))
    a = {'princ': Counter(), 'co': Counter(), 'lp': 0, 'lc': 0, 'leis': [], 'ult': [], 'casa_fonte': 'Senado'}
    for x in SEN[r['senado']]:
        dt = (x.get('dataApresentacao') or '')[:10]
        if dt < '2023-02-01': continue
        sig = (x.get('identificacao') or '').split(' ')[0]
        mm = first_re.match(x.get('autoria') or '')
        princ = bool(mm) and nrm(mm.group(1)) == nm
        num, _, ano = (x.get('identificacao') or ' / ').split(' ', 1)[-1].partition('/')
        p = {'t': sig, 'n': num, 'a': ano, 'd': dt, 'e': (x.get('ementa') or '').strip(), 's': x.get('situacaoAtual') or '',
             'u': f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{x.get('codigoMateria')}"}
        if princ:
            a['princ'][dt[:7]] += 1
            if sig in LEI: a['lp'] += 1; a['ult'].append(p)
        else:
            a['co'][dt[:7]] += 1
            if sig in LEI: a['lc'] += 1
        if (x.get('situacaoAtual') or '').upper().startswith('TRANSFORMADA EM NORMA') and sig in LEI:
            a['leis'].append(dict(p, papel='autor principal' if princ else 'coautor'))
    sen[pid] = a
print('Senado:', len(sen), 'senadores com processos;', sum(1 for v in SEN.values() if v is None), 'falhas de download')

# ---------- Falas ----------
def disc_cam(i):
    c = Counter(); page = 1
    while page < 60:
        u = f'https://dadosabertos.camara.leg.br/api/v2/deputados/{i}/discursos?dataInicio=2023-02-01&dataFim=2026-12-31&itens=100&pagina={page}&ordenarPor=dataHoraInicio&ordem=ASC'
        try: d = json.loads(curl(u))['dados']
        except Exception: return i, None
        for x in d: c[(x.get('dataHoraInicio') or '')[:7]] += 1
        if len(d) < 100: break
        page += 1
    return i, dict(c)
def disc_sen(c):
    cnt = Counter()
    for y in ANOS:
        try:
            d = json.loads(curl(f'https://legis.senado.leg.br/dadosabertos/senador/{c}/discursos?dataInicio={y}0101&dataFim={y}1231', json_hdr=True))
            d = d['DiscursosParlamentar']['Parlamentar'].get('Pronunciamentos', {}).get('Pronunciamento', [])
        except Exception: continue
        if isinstance(d, dict): d = [d]
        for x in d:
            dt = x.get('DataPronunciamento', '')[:7]
            if dt >= '2023-02': cnt[dt] += 1
    return c, dict(cnt)
with cf.ThreadPoolExecutor(8) as ex:
    DC = dict(ex.map(disc_cam, sorted(cam2pid)))
    DS = dict(ex.map(disc_sen, codes))
print('Falas: falhas na Câmara', sum(1 for v in DC.values() if v is None))

# ---------- Monta os datasets ----------
P = json.load(open(R + '/data/parlamentares.json'))
old = {x['id']: x for x in json.load(open(R + '/data/atividade.json'))}
def merge(a, b):
    c = Counter(a or {}); c.update(b or {}); return dict(c)
MON = [f'{y}-{mm:02d}' for y in ANOS for mm in range(1, 13) if f'{y}-{mm:02d}' >= '2023-02']
yrs = lambda dd: [sum(v for k, v in dd.items() if k.startswith(str(y))) for y in ANOS]
cut = lambda e: (e[:95] + '…') if len(e) > 96 else e
uid = lambda u: ('c' + u.split('idProposicao=')[1]) if 'idProposicao=' in u else ('s' + u.rsplit('/', 1)[1])
ativ, listas = [], []
for p in P:
    pid = p['id']; r = m.get(pid, {})
    row = {'id': pid, 'f': (old.get(pid) or {}).get('f')}
    if 'camara' in r: row['cam'] = r['camara']
    if 'senado' in r: row['sen'] = r['senado']
    A = [x for x in (cam.get(pid), sen.get(pid)) if x]
    if A:
        pr, co, lp, lc, leis, ult = {}, {}, 0, 0, [], []
        for x in A:
            pr = merge(pr, x['princ']); co = merge(co, x['co']); lp += x['lp']; lc += x['lc']; leis += x['leis']; ult += x['ult']
        dd = merge(DC.get(str(r.get('camara'))) if 'camara' in r else {}, DS.get(r.get('senado')) if 'senado' in r else {})
        if ('camara' in r and DC.get(str(r['camara'])) is None) and pid in old:   # falha de download: mantém as falas antigas
            row['d'] = old[pid].get('d')
        else:
            row['d'] = yrs(dd)
        ult.sort(key=lambda q: q['d'], reverse=True); leis.sort(key=lambda q: q['d'], reverse=True)
        seen, L = set(), []
        for l in leis:
            k = (l['t'], l['n'], l['a'])
            if k not in seen: seen.add(k); L.append(l)
        row.update({'p': ','.join(str(pr.get(k, 0)) for k in MON), 'c': yrs(co), 'lp': lp, 'lc': lc, 'nl': len(L),
                    'cf': '+'.join(x['casa_fonte'] for x in A)})
        row = {k: row[k] for k in ['id', 'f', 'cam', 'sen', 'p', 'c', 'lp', 'lc', 'd', 'nl', 'cf'] if k in row}
        listas.append({'id': pid,
                       'u': [[f"{q['t']} {q['n']}/{q['a']}", q['d'], cut(q['e']), uid(q['u'])] for q in ult[:3]],
                       'l': [[f"{q['t']} {q['n']}/{q['a']}", q['d'], cut(q['e']), uid(q['u']), 1 if q['papel'] == 'autor principal' else 0] for q in L[:3]]})
    elif pid in old and 'p' in old[pid]:   # sumiu por falha de download: mantém a linha antiga
        row = old[pid]
    ativ.append(row)
for name, data in (('atividade', ativ), ('atividade_listas', listas)):
    s = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    open(f'{R}/data/{name}.json', 'w').write(s)
    print(name, len(data), 'linhas,', round(len(s.encode()) / 1024), 'KB')
