# controlloqualita/helpers.py
from collections import defaultdict
from datetime import date, timedelta
import datetime as _dt
from django.db.models import Q
import random

CATS = ['EREDI', 'DOSSIER_BACC', 'DOSSIER_PL', 'RINTRACCI', 'ALTRO']
SCORE_MAP = {'P1': 6, 'P2': 10, 'N1': 5, 'N2': 3, 'P': 10, 'N': 3}


PALETTE = [
    "#0d6efd", "#6f42c1", "#dc3545", "#fd7e14",
    "#198754", "#20c997", "#0dcaf0", "#6610f2"
]

def _rnd():                                       # colore a rotazione
    while True:
        for c in PALETTE:
            yield c
_COL = _rnd()

# ---------- parser date ----------
def parse_data_aaaammgg(s):
    s = (s or '').strip()
    if len(s) != 8:
        return None
    try:
        return _dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None

def parse_data_ddmmyyyy_hhmmss(s):
    s = (s or '').strip()
    if not s:
        return None
    try:
        d, m, y = s.split()[0].split('/')
        return _dt.date(int(y), int(m), int(d))
    except ValueError:
        return None

# ---------- funzioni “public” ----------
def apply_filters(qs, cd):
    """filtra il queryset come in dashboard."""
    if cd.get('date_from'):
        qs = qs.filter(data_evasione__gte=cd['date_from'])
    if cd.get('date_to'):
        qs = qs.filter(data_evasione__lte=cd['date_to'])
    if cd.get('client'):
        qs = qs.filter(ragione_sociale_cliente__in=cd['client'])
    if cd.get('redattore'):
        qs = qs.filter(operatore__in=cd['redattore'])
    return qs

def build_kpi_structures(qs, get_cat, calc_score):
    """
    Restituisce un dict **JSON-serializzabile** con:
        qualita   → barre medie 0-10
        tempi     → % SLA
        torte     → conteggi esiti (lettere)
        trend     → media qualità (4 bucket) per categoria
    """
    # ---------- init strutture ----------
    qualita_sum = defaultdict(lambda: defaultdict(list))
    tempi_arr   = defaultdict(lambda: defaultdict(list))
    pie_counts  = defaultdict(lambda: defaultdict(int))
    trend_raw   = defaultdict(lambda: defaultdict(list))

    # ---------- loop record ----------
    for r in qs:
        cat = get_cat(r.servizio)
        if cat not in CATS:
            cat = 'ALTRO'

        let, num = calc_score(r, cat)          # (lettera, valore)

        cli = r.ragione_sociale_cliente or "?"
        qualita_sum[cli][cat].append(num)

        di = parse_data_aaaammgg   (r.raw_data.get('DataInserimento', ''))
        de = parse_data_aaaammgg   (r.raw_data.get('DataEvasione',    ''))
        ds = parse_data_ddmmyyyy_hhmmss(r.raw_data.get('DataScadenza', ''))

        in_time = None
        if de and ds:
            in_time = de <= ds
        tempi_arr[cli][cat].append(in_time)

        pie_counts[cat][let] += 1

        # ------------- trend -------------
        # prendiamo la data scadenza (se manca usiamo evasione o oggi)
        d_key = ds or de or date.today()
        trend_raw[cat][d_key].append(num)

    # ---------- trend bucket a 4 segmenti ----------
    trend_bucket = {}
    if qs:
        d_min = qs.order_by('data_evasione').first().data_evasione or date.today()
        d_max = qs.order_by('-data_evasione').first().data_evasione or date.today()
        span  = (d_max - d_min) / 4
        bucket_start = [ (d_min + i*span).replace(day=1) if span.days>30 else d_min+i*span
                         for i in range(4) ]

        for cat in CATS:
            vals = []
            for i in range(4):
                low = bucket_start[i]
                high = d_max if i==3 else bucket_start[i+1]-timedelta(days=1)
                # prendi tutti i valori raw nel range
                v = [x for d,lst in trend_raw[cat].items() if low<=d<=high for x in lst]
                media = round(sum(v)/len(v),2) if v else None
                label = f"{low.strftime('%d/%m')}-{high.strftime('%d/%m')}"
                vals.append({"label":label, "value":media})
            trend_bucket[cat] = vals

    # ---------- packing ----------
    return {
        "qualita" : _pack_bar(qualita_sum),
        "tempi"   : _pack_tempi(tempi_arr),
        "torte"   : {c:_pack_pie(v) for c,v in pie_counts.items()},
        "trend_raw"   : trend_bucket,
    }

# ---------- helper grafici ----------
def _pack_bar(dic):
    labels   = CATS
    datasets = []
    for cli, percat in dic.items():
        datasets.append({
            "label"           : cli,
            "data"            : [round(sum(percat.get(c, []))/max(len(percat.get(c,[])),1),2) for c in labels],
            "backgroundColor" : next(_COL)
        })
    return {"labels": labels, "datasets": datasets}

def _pack_tempi(dic):
    labels   = CATS
    datasets = []
    for cli, percat in dic.items():
        vals = []
        for c in labels:
            L     = [b for b in percat.get(c,[]) if b is not None]
            tot   = len(L)
            in_t  = L.count(True)
            perc  = round(in_t/tot*100,2) if tot else 0
            vals.append(perc)
        datasets.append({
            "label"           : cli,
            "data"            : vals,
            "backgroundColor" : next(_COL)
        })
    return {"labels": labels, "datasets": datasets}

def _pack_pie(d):
    return {
        "labels": list(d.keys()),
        "datasets": [{
            "data"           : [d[k] for k in d],
            "backgroundColor": [next(_COL) for _ in d]
        }]
    }
def _pack_trend(trend_raw, buckets):
    """
    Restituisce un dict:
        {"labels": [...],   # le 4 date-bucket in stringa
         "datasets":[
             {"name": "EREDI",        "values":[...], "color":"#4285F4"},
             ...
         ]}
    Se buckets è vuoto, restituisce {"labels":[], "datasets":[]}
    """
    if not buckets:          # nessun dato
        return {"labels": [], "datasets": []}

    for cat, val in trend_raw.items():
        if isinstance(val, list):
            trend_raw[cat] = {e['label']: e['value'] for e in val}

    # palette semplice, 1 colore per categoria
    palette = {
        'EREDI'       : '#0064B7',
        'DOSSIER_BACC': '#008A2E',
        'DOSSIER_PL'  : '#E07A00',
        'RINTRACCI'   : '#8B1A8B',
        'ALTRO'       : '#666666',
    }
    print('trend')
    print(trend_raw)
    print('buckets')
    print(buckets)
    #input()
    datasets = []
    for cat in CATS:
        print(cat)
        per_date = trend_raw.get(cat, {})
        print(per_date)
        # per ogni bucket prendi il valore più vicino (o None)
        vals = []
        last_val = None
        for lbl in buckets:
            v = per_date.get(lbl)
            if v is None:
                # linea continua: usa l’ultimo valore noto
                vals.append(last_val)
            else:
                last_val = v
                vals.append(v)
        datasets.append({
            "name"  : cat,
            "values": vals,
            "color" : palette.get(cat, '#999999')
        })

    return {"labels": buckets, "datasets": datasets}
    