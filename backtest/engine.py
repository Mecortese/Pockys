"""Réplica en Python de SMC_MTF_Bollinger_Strategy.pine (valores por defecto + parámetros ajustables).

Reproduce la lógica del script barra a barra:
  - Datos HTF (confirmación / macro) sólo de velas CERRADAS (equivalente a expr[1] + lookahead_on).
  - Estructura por fractales (BOS / CHOCH), Bollinger, ATR, ADX, FVG, barridos de liquidez.
  - Motores: Pullback BB confirmado con CHOCH, Scalp CHOCH (filtrado por tipo mínimo) y Modo rango.
  - Filtros: tipo mínimo, recorrido hasta zona de liquidez HTF, riesgo mínimo (ATR / comisión), pausa tras pérdida.
  - Gestión: tamaño por riesgo, salidas por zonas de liquidez / TP fijo / parcial + runner, breakeven, CHOCH en contra.
  - Ejecución estilo TradingView: señal al cierre, entrada a la apertura siguiente, stops/límites dentro de la vela
    con el recorrido O->H->L->C u O->L->H->C según qué extremo esté más cerca de la apertura.
"""
import math
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

NA = float("nan")


def isna(x):
    return x is None or x != x


# ---------------------------------------------------------------------------------------------------
# Parámetros (mismos nombres y valores por defecto que los inputs del script)
# ---------------------------------------------------------------------------------------------------
@dataclass
class Params:
    bbLen: int = 20
    bbMult: float = 2.0
    pivLenHTF: int = 3
    use4hBasisFilter: bool = True
    use1hStructure: bool = True
    # motores
    useRS: bool = False             # Respaldo D+macro+conf con gatillos CHOCH+liquidez / ruptura BB
    rsAntic: bool = True
    rsBeR: float = 1.0
    rsTargetR: float = 3.0
    useBreakout: bool = False       # Ruptura de banda BB a favor de la tendencia HTF
    breakoutTrendMode: str = "tendencia"   # "tendencia" (estructura conf+macro y precio vs media macro) | "macro"
    rrBreakout: float = 3.0
    usePullback: bool = True
    useScalp: bool = True
    allowLong: bool = True
    allowShort: bool = True
    # scalp CHOCH
    pivLenScalp: int = 2
    scalpReqLiq: bool = True
    scalpLiqLookback: int = 15
    scalpSlLookback: int = 10
    scalpSlAtrBuf: float = 0.3
    scalpMaxRiskAtr: float = 3.0
    allowReverse: bool = True
    scalpCloseOnLtfChoch: bool = True
    blockCounterScalps: bool = True
    # SMC / liquidez
    pivLenLTF: int = 5
    nearBandAtr: float = 1.0
    maxFvgBoxes: int = 20
    # filtros de calidad
    useAdxFilter: bool = True
    adxMin: float = 20.0
    adxLen: int = 14
    pbTurnWindow: int = 20
    minRiskAtr: float = 0.5
    commPct: float = 0.04
    minRiskCost: float = 4.0
    widenStops: bool = True
    cooldownBars: int = 6
    minTier: int = 2
    # modo rango
    useRangeMode: bool = True
    rangeZonePct: float = 25.0
    rangeTargetMid: bool = True
    rangeMinRR: float = 1.0
    # riesgo
    riskPct: float = 0.5
    maxLeverage: float = 2.0
    atrLen: int = 14
    slAtrMult: float = 1.0
    rrScalp: float = 1.5
    rrIntra: float = 2.0
    rrSwing: float = 3.0
    exitMode: str = "liq"          # "liq" | "fixed" | "runner" | "runner_trail"
    trailAtrBO: float = 3.0
    useRoomFilter: bool = True
    minRoomR: float = 2.0
    useMidObs: bool = False
    runnerTrailAtr: float = 3.0
    partialPct: float = 50.0
    partialAtR: float = 2.0
    moveToBE: bool = True
    beAtR: float = 1.5
    beCostMult: float = 1.5
    allowUpgrade: bool = True
    closeOnChoch: bool = True
    # simulación
    initialCapital: float = 10000.0
    commSim: float = -1.0          # comisión simulada (% por lado); -1 = igual que commPct


# ---------------------------------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------------------------------
def rma(x, n):
    out = np.full(len(x), np.nan)
    s, cnt, prev = 0.0, 0, np.nan
    for i, v in enumerate(x):
        if v != v:
            continue
        if cnt < n:
            s += v
            cnt += 1
            if cnt == n:
                prev = s / n
                out[i] = prev
        else:
            prev = (prev * (n - 1) + v) / n
            out[i] = prev
    return out


def true_range(h, l, c):
    pc = np.roll(c, 1)
    pc[0] = np.nan
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def bollinger(c, n, mult):
    s = pd.Series(c)
    mid = s.rolling(n).mean().values
    sd = s.rolling(n).std(ddof=0).values
    return mid, mid + mult * sd, mid - mult * sd


def adx(h, l, c, n):
    up = np.diff(h, prepend=np.nan)
    dn = -np.diff(l, prepend=np.nan)
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    plus[0] = minus[0] = np.nan
    tr = true_range(h, l, c)
    trur = rma(tr, n)
    p = 100 * rma(plus, n) / trur
    m = 100 * rma(minus, n) / trur
    s = p + m
    return 100 * rma(np.abs(p - m) / np.where(s == 0, 1, s), n)


def pivots(h, l, L):
    """ta.pivothigh / ta.pivotlow: valor confirmado en la barra i (pivote en i-L)."""
    n = len(h)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for i in range(2 * L, n):
        c = i - L
        wh = h[i - 2 * L:i + 1]
        wl = l[i - 2 * L:i + 1]
        if h[c] == wh.max() and (wh[:L] < h[c]).all() and (wh[L + 1:] <= h[c]).all():
            ph[i] = h[c]
        if l[c] == wl.min() and (wl[:L] > l[c]).all() and (wl[L + 1:] >= l[c]).all():
            pl[i] = l[c]
    return ph, pl


def market_structure(h, l, c, piv):
    """f_ms: tendencia, evento (1 BOS↑, 2 CHOCH↑, -1 BOS↓, -2 CHOCH↓), contador, nivel, swings."""
    ph, pl = pivots(h, l, piv)
    n = len(c)
    tr = np.zeros(n)
    ev = np.zeros(n)
    evc = np.zeros(n)
    evl = np.full(n, np.nan)
    sh_a = np.full(n, np.nan)
    sl_a = np.full(n, np.nan)
    sh = sl = np.nan
    hb = lb = True
    trend, et, ec, el = 0, 0, 0, np.nan
    for i in range(n):
        if ph[i] == ph[i]:
            sh, hb = ph[i], False
        if pl[i] == pl[i]:
            sl, lb = pl[i], False
        if not hb and c[i] > sh:
            hb = True
            et = 1 if trend == 1 else 2
            el, ec, trend = sh, ec + 1, 1
        elif not lb and c[i] < sl:
            lb = True
            et = -1 if trend == -1 else -2
            el, ec, trend = sl, ec + 1, -1
        tr[i], ev[i], evc[i], evl[i], sh_a[i], sl_a[i] = trend, et, ec, el, sh, sl
    return tr, ev, evc, evl, sh_a, sl_a


# ---------------------------------------------------------------------------------------------------
# Datos y timeframes
# ---------------------------------------------------------------------------------------------------
TF_RULE = {"5": "5min", "15": "15min", "60": "1h", "240": "4h", "D": "1D", "W": "W-MON"}


def resample(df5, tf):
    if tf == "5":
        return df5.copy()
    rule = TF_RULE[tf]
    kw = dict(label="left", closed="left")
    o = df5.resample(rule, **kw).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return o.dropna()


def bucket(index, tf):
    if tf == "W":
        d = index.normalize()
        return d - pd.to_timedelta(d.weekday, unit="D")
    return index.floor(TF_RULE[tf].replace("1D", "D"))


def auto_htf(tf):
    sec = {"5": 300, "15": 900, "60": 3600, "240": 14400}[tf]
    if sec <= 1800:
        return "60", "240"
    if sec <= 3600:
        return "240", "D"
    return "D", "W"


def htf_features(dfh, p):
    h, l, c = dfh.high.values, dfh.low.values, dfh.close.values
    mid, up, lo = bollinger(c, p.bbLen, p.bbMult)
    ax = adx(h, l, c, p.adxLen)
    tr, ev, evc, evl, sh, sl = market_structure(h, l, c, p.pivLenHTF)
    n = len(c)
    bt, bb, st, sb = (np.full(n, np.nan) for _ in range(4))
    _bt = _bb = _st = _sb = np.nan
    for i in range(n):
        if i >= 2 and l[i] > h[i - 2]:
            _bt, _bb = l[i], h[i - 2]
        if i >= 2 and h[i] < l[i - 2]:
            _st, _sb = l[i - 2], h[i]
        if _bb == _bb and c[i] < _bb:
            _bt = _bb = np.nan
        if _st == _st and c[i] > _st:
            _st = _sb = np.nan
        bt[i], bb[i], st[i], sb[i] = _bt, _bb, _st, _sb
    return dict(tr=tr, ev=ev, evc=evc, evl=evl, mid=mid, up=up, lo=lo, cl=c, bfT=bt, bfB=bb, sfT=st, sfB=sb,
                adx=ax, swH=sh, swL=sl)


def map_htf(ltf_index, dfh, feats, tf):
    """Valor de la vela HTF anterior (cerrada) para cada vela del gráfico."""
    b = bucket(ltf_index, tf)
    k = dfh.index.get_indexer(b)
    out = {}
    for key, arr in feats.items():
        v = np.full(len(k), np.nan)
        ok = k >= 1
        v[ok] = arr[k[ok] - 1]
        out[key] = v
    return out


# ---------------------------------------------------------------------------------------------------
# Broker (emulación del Probador de Estrategias)
# ---------------------------------------------------------------------------------------------------
@dataclass
class Trade:
    direction: int
    entry_time: object
    entry_price: float
    qty: float
    category: str
    legs: list = field(default_factory=list)   # (time, price, qty, pnl, reason)

    @property
    def pnl(self):
        return sum(x[3] for x in self.legs)


class Sim:
    def __init__(self, df5, tf, p: Params, start=None, end=None):
        self.p, self.tf = p, tf
        self._base5 = df5
        self.df = resample(df5, tf)
        self.tfC, self.tfM = auto_htf(tf)
        self.start, self.end = start, end
        self._prep()

    # --- precálculo vectorial ---
    def _prep(self):
        p, d = self.p, self.df
        o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.o, self.h, self.l, self.c = o, h, l, c
        self.t = d.index
        self.bbMid, self.bbUp, self.bbLo = bollinger(c, p.bbLen, p.bbMult)
        self.atr = rma(true_range(h, l, c), p.atrLen)
        self.trL, self.evL, self.evcL, self.evlL, _, _ = market_structure(h, l, c, p.pivLenScalp)
        self.phL, self.plL = pivots(h, l, p.pivLenLTF)
        src = self._base5
        H = {}
        for key, tf in (("C", self.tfC), ("M", self.tfM)):
            dfh = resample(src, tf)
            H[key] = map_htf(self.t, dfh, htf_features(dfh, p), tf)
        self.H1, self.H4 = H["C"], H["M"]
        n = len(c)
        s = pd.Series
        self.lowestSc = s(l).rolling(p.scalpSlLookback, min_periods=1).min().values
        self.highestSc = s(h).rolling(p.scalpSlLookback, min_periods=1).max().values
        self.lowestPb = s(l).rolling(p.pbTurnWindow, min_periods=1).min().values
        self.highestPb = s(h).rolling(p.pbTurnWindow, min_periods=1).max().values
        self.lo10 = s(l).rolling(10, min_periods=1).min().values
        self.hi10 = s(h).rolling(10, min_periods=1).max().values
        if p.useRS:
            from be5 import daily_trend
            D = daily_trend(src, self.t)
            self.dUp, self.dTr = D["dUp"].values, D["dTr"].values
            d15 = resample(src, "15")
            t15, *_ = market_structure(d15.high.values, d15.low.values, d15.close.values, 2)
            self.tr15 = map_htf(self.t, d15, {"tr": t15}, "15")["tr"] if self.tf == "5" else np.full(len(c), np.nan)
        self.lo5 = s(l).rolling(5, min_periods=1).min().values
        self.hi5 = s(h).rolling(5, min_periods=1).max().values

    # --- utilidades por barra ---
    def next_level(self, i, px, direction, gap):
        H1, H4, p = self.H1, self.H4, self.p
        lv = (H1["up"][i], H1["lo"][i], H4["up"][i], H4["lo"][i], H1["swH"][i], H1["swL"][i], H4["swH"][i], H4["swL"][i])
        if p.useMidObs:
            lv = lv + (H1["mid"][i], H4["mid"][i])
        best = NA
        for v in lv:
            if v == v and (v > px + gap if direction == 1 else v < px - gap):
                if best != best or (v < best if direction == 1 else v > best):
                    best = v
        return best

    def run(self):
        p = self.p
        o, h, l, c, t = self.o, self.h, self.l, self.c, self.t
        H1, H4 = self.H1, self.H4
        n = len(c)
        atr, bbUp, bbLo = self.atr, self.bbUp, self.bbLo
        trL, evL, evcL, evlL = self.trL, self.evL, self.evcL, self.evlL
        start = pd.Timestamp(self.start, tz="UTC") if self.start else None
        end = pd.Timestamp(self.end, tz="UTC") if self.end else None

        def rr(tier):
            if posRS:
                return p.rsTargetR
            if posBO:
                return p.rrBreakout
            return p.rrSwing if tier == 3 else p.rrIntra if tier == 2 else p.rrScalp

        def align1(i, d):
            return H1["tr"][i] == d

        def align4(i, d):
            if H4["tr"][i] != d:
                return False
            if not p.use4hBasisFilter:
                return True
            return H4["cl"][i] > H4["mid"][i] if d == 1 else H4["cl"][i] < H4["mid"][i]

        def adx_ok(i):
            a = H1["adx"][i]
            return (not p.useAdxFilter) or (a == a and a >= p.adxMin)

        def tier(i, d):
            base = 3 if (align1(i, d) and align4(i, d)) else 2 if align1(i, d) else 1
            return base if adx_ok(i) else min(base, 2)

        cost = lambda px: 2 * p.commPct / 100 * px
        comm = (p.commPct if p.commSim < 0 else p.commSim) / 100

        # ---- estado del script ----
        ltfSH = ltfSL = NA
        bullF, bearF = [], []                 # FVG LTF: [top, bot]
        lastBullLiq = lastBearLiq = None
        bullLiqLow = bearLiqHigh = NA
        last = dict(touchLo=None, touchUp=None, scBull=None, scBear=None, lowZ=None, highZ=None)
        posDir = posTier = 0
        posRange = False
        entryRef = stopPrice = targetPrice = riskR = initQty = NA
        pending = False
        pendingBar = None
        partialDone = beDone = False
        tp1Liq = tp2Liq = NA
        posBO = False
        posRS = False
        extreme = NA
        lastLossL = lastLossS = None
        # ---- estado del broker ----
        equity = p.initialCapital
        pos = 0.0          # cantidad con signo
        avg = NA
        cur = None         # Trade abierto
        trades = []
        entry_order = None   # (dir, qty, category)
        close_order = False
        exits = None         # dict(tp1=(qty, limit), tp2=(limit), stop=)
        eq_curve = np.full(n, np.nan)
        prevEvc1 = H1["evc"][0]

        def fill(price, qty, reason, i):
            """Cierra qty (>0) de la posición al precio dado."""
            nonlocal pos, equity, cur, avg
            d = 1 if pos > 0 else -1
            qty = min(qty, abs(pos))
            pnl = d * (price - avg) * qty - comm * price * qty
            equity += pnl
            pos -= d * qty
            cur.legs.append((t[i], price, qty, pnl, reason))
            if abs(pos) < 1e-12:
                pos = 0.0
                trades.append(cur)
                cur = None
            return d, pnl

        for i in range(n):
            closed_legs = []
            # =============== BROKER: apertura de la vela ===============
            if close_order and pos != 0:
                closed_legs.append(fill(o[i], abs(pos), "CHOCH", i))
                exits = None
            close_order = False
            if entry_order is not None:
                d, qty, cat = entry_order
                if pos != 0 and (1 if pos > 0 else -1) != d:     # reversa
                    closed_legs.append(fill(o[i], abs(pos), "Reversa", i))
                if pos == 0 and qty and qty > 0:
                    pos, avg = d * qty, o[i]
                    equity -= comm * o[i] * qty
                    cur = Trade(d, t[i], o[i], qty, cat)
                    cur.legs.append((t[i], o[i], 0.0, -comm * o[i] * qty, "entrada"))
                entry_order = None
            # =============== BROKER: stops / límites dentro de la vela ===============
            if pos != 0 and exits is not None:
                d = 1 if pos > 0 else -1
                path = [o[i], h[i], l[i], c[i]] if abs(h[i] - o[i]) < abs(o[i] - l[i]) else [o[i], l[i], h[i], c[i]]
                stop = exits["stop"]
                lims = []   # [precio, qty (None = resto), motivo]
                if exits.get("tp1") is not None and exits["tp1"][1] == exits["tp1"][1]:
                    lims.append([exits["tp1"][1], exits["tp1"][0], "TP1"])
                if exits.get("tp2") is not None and exits["tp2"] == exits["tp2"]:
                    lims.append([exits["tp2"], None, "TP2"])
                lims.sort(key=lambda x: x[0] * d)

                def take_limits(lo_, hi_, at_open):
                    for lim in lims:
                        if pos == 0 or lim[1] == 0:
                            continue
                        lp = lim[0]
                        if (d == 1 and (lp <= hi_ if at_open else lo_ < lp <= hi_)) or (d == -1 and (lp >= lo_ if at_open else lo_ <= lp < hi_)):
                            px_ = o[i] if at_open else lp
                            q = abs(pos) if lim[1] is None else min(lim[1], abs(pos))
                            closed_legs.append(fill(px_, q, lim[2], i))
                            lim[1] = 0
                            if lim[2] == "TP1":
                                exits["tp1"] = None

                # apertura: gaps a través del stop o del límite
                if stop == stop and ((d == 1 and o[i] <= stop) or (d == -1 and o[i] >= stop)):
                    closed_legs.append(fill(o[i], abs(pos), "Stop", i))
                else:
                    take_limits(o[i], o[i], True)
                    for k in range(1, 4):
                        if pos == 0:
                            break
                        a_, b_ = path[k - 1], path[k]
                        favor = (b_ > a_) if d == 1 else (b_ < a_)
                        if favor:
                            take_limits(min(a_, b_), max(a_, b_), False)
                        elif stop == stop and ((d == 1 and b_ <= stop < a_) or (d == -1 and a_ < stop <= b_)):
                            closed_legs.append(fill(stop, abs(pos), "Stop", i))
                            break
            if pos == 0:
                exits = None
            # mark to market
            eq_curve[i] = equity + ((pos * (c[i] - avg)) if pos != 0 else 0.0)
            for d_, pnl_ in closed_legs:
                if pnl_ < 0:
                    if d_ == 1:
                        lastLossL = i
                    else:
                        lastLossS = i

            # =============== SCRIPT al cierre de la vela ===============
            a_ = atr[i]
            if a_ != a_ or H1["tr"][i] != H1["tr"][i] or H4["tr"][i] != H4["tr"][i] or bbUp[i] != bbUp[i]:
                continue
            inRange = (start is None or t[i] >= start) and (end is None or t[i] < end)
            up1, lo1, mid1 = H1["up"][i], H1["lo"][i], H1["mid"][i]
            up4, lo4 = H4["up"][i], H4["lo"][i]
            evc1 = H1["evc"][i]
            newEvt1h = evc1 != prevEvc1
            prevEvc1 = evc1
            bullChoch1h = newEvt1h and H1["ev"][i] == 2
            bearChoch1h = newEvt1h and H1["ev"][i] == -2
            newEvtL = i > 0 and evcL[i] != evcL[i - 1]
            bullChochL = newEvtL and evL[i] == 2
            bearChochL = newEvtL and evL[i] == -2

            # swings de liquidez LTF y barridos
            if self.phL[i] == self.phL[i]:
                ltfSH = self.phL[i]
            if self.plL[i] == self.plL[i]:
                ltfSL = self.plL[i]
            sweepLow = ltfSL == ltfSL and l[i] < ltfSL and c[i] > ltfSL
            sweepHigh = ltfSH == ltfSH and h[i] > ltfSH and c[i] < ltfSH
            if sweepLow:
                ltfSL = NA
            if sweepHigh:
                ltfSH = NA

            # FVG LTF
            newBull = i >= 2 and l[i] > h[i - 2]
            newBear = i >= 2 and h[i] < l[i - 2]
            if newBull:
                bullF.append([l[i], h[i - 2]])
                if len(bullF) > p.maxFvgBoxes:
                    bullF.pop(0)
            if newBear:
                bearF.append([l[i - 2], h[i]])
                if len(bearF) > p.maxFvgBoxes:
                    bearF.pop(0)
            tBullF = tBearF = False
            for j in range(len(bullF) - 1, -1, -1):
                tp_, bt_ = bullF[j]
                if newBull and j == len(bullF) - 1:
                    continue
                if l[i] <= tp_ and h[i] >= bt_:
                    tBullF = True
                if c[i] < bt_:
                    bullF.pop(j)
            for j in range(len(bearF) - 1, -1, -1):
                tp_, bt_ = bearF[j]
                if newBear and j == len(bearF) - 1:
                    continue
                if h[i] >= bt_ and l[i] <= tp_:
                    tBearF = True
                if c[i] > tp_:
                    bearF.pop(j)
            bfT1, bfB1, sfT1, sfB1 = H1["bfT"][i], H1["bfB"][i], H1["sfT"][i], H1["sfB"][i]
            tBullF1 = bfT1 == bfT1 and l[i] <= bfT1 and h[i] >= bfB1
            tBearF1 = sfB1 == sfB1 and h[i] >= sfB1 and l[i] <= sfT1

            # --- Motor pullback ---
            bullTrend = align4(i, 1) and (not p.use1hStructure or align1(i, 1))
            bearTrend = align4(i, -1) and (not p.use1hStructure or align1(i, -1))
            touchLower = l[i] <= bbLo[i]
            touchUpper = h[i] >= bbUp[i]
            if touchLower:
                last["touchLo"] = i
            if touchUpper:
                last["touchUp"] = i
            nearLower = l[i] <= bbLo[i] + p.nearBandAtr * a_
            nearUpper = h[i] >= bbUp[i] - p.nearBandAtr * a_
            bullLiqEvent = nearLower and (sweepLow or tBullF or tBullF1 or (lo1 == lo1 and l[i] <= lo1) or (lo4 == lo4 and l[i] <= lo4))
            bearLiqEvent = nearUpper and (sweepHigh or tBearF or tBearF1 or (up1 == up1 and h[i] >= up1) or (up4 == up4 and h[i] >= up4))
            if bullLiqEvent:
                lastBullLiq = i
            if bearLiqEvent:
                lastBearLiq = i
            win = p.pbTurnWindow
            tLoWin = last["touchLo"] is not None and i - last["touchLo"] <= win
            tUpWin = last["touchUp"] is not None and i - last["touchUp"] <= win
            liqBW = lastBullLiq is not None and i - lastBullLiq <= win
            liqSW = lastBearLiq is not None and i - lastBearLiq <= win
            pbLongSetup = p.usePullback and bullTrend and bullChochL and tLoWin and liqBW
            pbShortSetup = p.usePullback and bearTrend and bearChochL and tUpWin and liqSW
            pbLongSl = self.lowestPb[i] - p.slAtrMult * a_
            pbShortSl = self.highestPb[i] + p.slAtrMult * a_

            # --- Motor scalp CHOCH ---
            scB = sweepLow or touchLower or tBullF or tBullF1 or (lo1 == lo1 and l[i] <= lo1)
            scS = sweepHigh or touchUpper or tBearF or tBearF1 or (up1 == up1 and h[i] >= up1)
            if scB:
                last["scBull"] = i
            if scS:
                last["scBear"] = i
            scBullOk = (not p.scalpReqLiq) or (last["scBull"] is not None and i - last["scBull"] <= p.scalpLiqLookback)
            scBearOk = (not p.scalpReqLiq) or (last["scBear"] is not None and i - last["scBear"] <= p.scalpLiqLookback)
            scLongSl = self.lowestSc[i] - p.scalpSlAtrBuf * a_
            scShortSl = self.highestSc[i] + p.scalpSlAtrBuf * a_
            px = c[i]
            scLRisk = px > scLongSl and (p.scalpMaxRiskAtr <= 0 or px - scLongSl <= p.scalpMaxRiskAtr * a_)
            scSRisk = scShortSl > px and (p.scalpMaxRiskAtr <= 0 or scShortSl - px <= p.scalpMaxRiskAtr * a_)
            tr1, tr4 = H1["tr"][i], H4["tr"][i]
            scLongSetup = p.useScalp and bullChochL and scBullOk and scLRisk and not (p.blockCounterScalps and tr1 == -1 and tr4 == -1)
            scShortSetup = p.useScalp and bearChochL and scBearOk and scSRisk and not (p.blockCounterScalps and tr1 == 1 and tr4 == 1)

            # --- Modo rango ---
            rangeRegime = p.useRangeMode and H1["adx"][i] == H1["adx"][i] and not adx_ok(i)
            bw = up1 - lo1
            if bw == bw and l[i] <= lo1 + bw * p.rangeZonePct / 100:
                last["lowZ"] = i
            if bw == bw and h[i] >= up1 - bw * p.rangeZonePct / 100:
                last["highZ"] = i
            rgLowRecent = last["lowZ"] is not None and i - last["lowZ"] <= win
            rgHighRecent = last["highZ"] is not None and i - last["highZ"] <= win
            rgLongTp = mid1 if p.rangeTargetMid else up1
            rgShortTp = mid1 if p.rangeTargetMid else lo1
            rgLongSetup = rangeRegime and bullChochL and rgLowRecent and scBullOk and px < rgLongTp
            rgShortSetup = rangeRegime and bearChochL and rgHighRecent and scBearOk and px > rgShortTp

            # --- Motor ruptura BB con tendencia ---
            if p.useBreakout and i > 0:
                if p.breakoutTrendMode == "tendencia":
                    tU = H4["tr"][i] == 1 and H4["cl"][i] > H4["mid"][i] and H1["tr"][i] == 1
                    tD = H4["tr"][i] == -1 and H4["cl"][i] < H4["mid"][i] and H1["tr"][i] == -1
                else:
                    tU, tD = H4["cl"][i] > H4["mid"][i], H4["cl"][i] < H4["mid"][i]
                boLong = tU and c[i] > bbUp[i] and c[i - 1] <= bbUp[i - 1]
                boShort = tD and c[i] < bbLo[i] and c[i - 1] >= bbLo[i - 1]
                boLongSl = min(self.lo5[i] - 0.5 * a_, c[i] - a_)
                boShortSl = max(self.hi5[i] + 0.5 * a_, c[i] + a_)
            else:
                boLong = boShort = False
                boLongSl = boShortSl = NA

            # --- Motor respaldo ---
            rsL = rsS = False
            if p.useRS and i > 0:
                dU, dT = self.dUp[i], self.dTr[i]
                respUp = dU == 1 and dT == 1 and H4["tr"][i] == 1 and H4["cl"][i] > H4["mid"][i] and H1["tr"][i] == 1
                respDn = dU == -1 and dT == -1 and H4["tr"][i] == -1 and H4["cl"][i] < H4["mid"][i] and H1["tr"][i] == -1
                bbCrossUp = c[i] > bbUp[i] and c[i - 1] <= bbUp[i - 1]
                bbCrossDn = c[i] < bbLo[i] and c[i - 1] >= bbLo[i - 1]
                antic = p.rsAntic and self.tf == "5"
                rsChL = bullChochL and scBullOk
                rsChS = bearChochL and scBearOk
                rsL = respUp and (rsChL or bbCrossUp) and (not antic or self.tr15[i] != 1)
                rsS = respDn and (rsChS or bbCrossDn) and (not antic or self.tr15[i] != -1)

            # --- 7.1 ejecución de la orden pendiente / cierre ---
            if pending and pos != 0 and (1 if pos > 0 else -1) == posDir:
                pending = False
                initQty = abs(pos)
                entryRef = avg
                riskR = abs(entryRef - stopPrice)
                if not posRange:
                    targetPrice = entryRef + posDir * riskR * rr(posTier)
            pendingExpired = pending and pos == 0 and i > pendingBar + 1
            if pendingExpired or (not pending and posDir != 0 and pos == 0):
                posDir = posTier = 0
                posRange = False
                pending = False
                entryRef = stopPrice = targetPrice = riskR = initQty = NA
                partialDone = beDone = False
                tp1Liq = tp2Liq = NA
                posBO = False
                posRS = False
                extreme = NA
                exits = None

            # --- 7.2 gestión ---
            inPos = (not pending) and posDir != 0 and pos != 0
            if inPos:
                if not partialDone and abs(pos) < initQty * 0.999:
                    partialDone = True
                nt = tier(i, posDir)
                if p.allowUpgrade and nt > posTier and not posRange:
                    posTier = nt
                    if p.exitMode != "liq":
                        targetPrice = entryRef + posDir * riskR * rr(posTier)
                extreme = (max(extreme, h[i]) if posDir == 1 else min(extreme, l[i])) if extreme == extreme else (h[i] if posDir == 1 else l[i])
                if p.exitMode == "runner_trail" and partialDone:
                    ts = extreme - posDir * p.trailAtrBO * a_
                    stopPrice = max(stopPrice, entryRef, ts) if posDir == 1 else min(stopPrice, entryRef, ts)
                if p.exitMode == "liq" and not posRange and not posBO:
                    t1 = self.next_level(i, entryRef, posDir, 0.0)
                    if t1 != t1:
                        t1 = entryRef + posDir * riskR * rr(posTier)
                    t1 = max(t1, entryRef + riskR) if posDir == 1 else min(t1, entryRef - riskR)
                    if not partialDone:
                        tp1Liq = t1
                    tp2Liq = self.next_level(i, tp1Liq if tp1Liq == tp1Liq else t1, posDir, 0.5 * riskR)
                    targetPrice = tp1Liq if tp2Liq != tp2Liq else tp2Liq
                    if partialDone:
                        be2 = entryRef + posDir * p.beCostMult * cost(entryRef)
                        tst = c[i] - posDir * p.runnerTrailAtr * a_
                        stopPrice = max(stopPrice, be2, tst) if posDir == 1 else min(stopPrice, be2, tst)
                if p.moveToBE and posTier >= 2 and not beDone:
                    beR = p.rsBeR if posRS else p.beAtR
                    reached = h[i] >= entryRef + riskR * beR if posDir == 1 else l[i] <= entryRef - riskR * beR
                    if reached:
                        beDone = True
                        bs = entryRef + posDir * p.beCostMult * cost(entryRef)
                        stopPrice = max(stopPrice, bs) if posDir == 1 else min(stopPrice, bs)
            exitLong = inPos and posDir == 1 and ((posTier == 1 and p.scalpCloseOnLtfChoch and bearChochL) or (posTier >= 2 and p.closeOnChoch and bearChoch1h and not posRS))
            exitShort = inPos and posDir == -1 and ((posTier == 1 and p.scalpCloseOnLtfChoch and bullChochL) or (posTier >= 2 and p.closeOnChoch and bullChoch1h and not posRS))

            # --- 7.3 señales ---
            coolL = p.cooldownBars == 0 or lastLossL is None or i - lastLossL > p.cooldownBars
            coolS = p.cooldownBars == 0 or lastLossS is None or i - lastLossS > p.cooldownBars
            flat = pos == 0
            canRevS = p.allowReverse and pos < 0 and posTier == 1
            canRevL = p.allowReverse and pos > 0 and posTier == 1
            longOk = p.allowLong and inRange and coolL and tier(i, 1) >= p.minTier
            shortOk = p.allowShort and inRange and coolS and tier(i, -1) >= p.minTier
            minD = max(p.minRiskAtr * a_, p.minRiskCost * cost(px))
            riskOk = lambda dist: dist > 0 and dist >= minD
            if p.widenStops:
                scLSlF, scSSlF = min(scLongSl, px - minD), max(scShortSl, px + minD)
                pbLSlF, pbSSlF = min(pbLongSl, px - minD), max(pbShortSl, px + minD)
            else:
                scLSlF, scSSlF, pbLSlF, pbSSlF = scLongSl, scShortSl, pbLongSl, pbShortSl

            def roomOk(sl, d):
                if not p.useRoomFilter:
                    return True
                nx = self.next_level(i, px, d, 0.0)
                risk = abs(px - sl)
                return nx != nx or (risk > 0 and abs(nx - px) >= p.minRoomR * risk)

            longScalp = longOk and scLongSetup and (flat or canRevS) and riskOk(px - scLSlF) and roomOk(scLSlF, 1)
            shortScalp = shortOk and scShortSetup and (flat or canRevL) and riskOk(scSSlF - px) and roomOk(scSSlF, -1)
            longPb = longOk and pbLongSetup and flat and riskOk(px - pbLSlF) and roomOk(pbLSlF, 1)
            shortPb = shortOk and pbShortSetup and flat and riskOk(pbSSlF - px) and roomOk(pbSSlF, -1)
            rgOkL = p.allowLong and inRange and coolL
            rgOkS = p.allowShort and inRange and coolS
            longRange = rgOkL and rgLongSetup and (flat or canRevS) and riskOk(px - scLSlF) and (rgLongTp - px) >= p.rangeMinRR * (px - scLSlF)
            shortRange = rgOkS and rgShortSetup and (flat or canRevL) and riskOk(scSSlF - px) and (px - rgShortTp) >= p.rangeMinRR * (scSSlF - px)
            longRS = p.allowLong and inRange and coolL and rsL and flat
            shortRS = p.allowShort and inRange and coolS and rsS and flat
            longBO = p.allowLong and inRange and coolL and boLong and flat
            shortBO = p.allowShort and inRange and coolS and boShort and flat
            longSignal = longScalp or longPb or longRange or longBO or longRS
            shortSignal = (not longSignal) and (shortScalp or shortPb or shortRange or shortBO or shortRS)

            for d, sig, isScalp, isPb, isRg, scSl, pbSl, rgTp, isBO, boSl in (
                    (1, longSignal, longScalp, longPb, longRange and not longScalp and not longPb, scLSlF, pbLSlF, rgLongTp, longBO or longRS, boLongSl if longBO else min(self.lo10[i] - 0.3 * a_, px - minD)),
                    (-1, shortSignal, shortScalp, shortPb, shortRange and not shortScalp and not shortPb, scSSlF, pbSSlF, rgShortTp, shortBO or shortRS, boShortSl if shortBO else max(self.hi10[i] + 0.3 * a_, px + minD))):
                if not sig:
                    continue
                posBO = isBO and not isScalp and not isPb and not isRg
                posRS = posBO and (longRS if d == 1 else shortRS) and not (longBO if d == 1 else shortBO)
                extreme = NA
                if posBO:
                    isScalp = isPb = False
                    pbSl = boSl
                posDir, posTier = d, (3 if posBO else tier(i, d))
                entryRef = px
                stopPrice = scSl if (isScalp and not isPb) else pbSl
                riskR = abs(entryRef - stopPrice)
                targetPrice = entryRef + d * riskR * rr(posTier)
                nl = self.next_level(i, entryRef, d, 0.0)
                tp1Liq = (max(targetPrice if nl != nl else nl, entryRef + riskR) if d == 1 else min(targetPrice if nl != nl else nl, entryRef - riskR)) if p.exitMode == "liq" else NA
                tp2Liq = self.next_level(i, tp1Liq, d, 0.5 * riskR) if p.exitMode == "liq" else NA
                pending, pendingBar = True, i
                initQty = NA
                partialDone = beDone = False
                if d == 1:
                    lastBullLiq = None
                else:
                    lastBearLiq = None
                posRange = isRg
                if isRg:
                    posTier, entryRef, stopPrice = 1, px, scSl
                    riskR = abs(entryRef - stopPrice)
                    targetPrice = rgTp
                    cat = "RANGO"
                elif posRS:
                    cat = "RESPALDO"
                elif posBO:
                    cat = "RUPTURA"
                else:
                    cat = ["", "SCALP", "INTRA", "SWING"][posTier] + (" PB" if isPb else " CH")
                eqNow = eq_curve[i]
                dist = abs(entryRef - stopPrice)
                qty = min(eqNow * p.riskPct / 100 / dist, eqNow * p.maxLeverage / entryRef) if dist > 0 else 0
                entry_order = (d, qty, cat)

            if (exitLong and not shortSignal) or (exitShort and not longSignal):
                close_order = True

            # --- 7.4 órdenes de salida ---
            if posDir != 0 and (pending or pos != 0):
                liqMode = p.exitMode == "liq" and not posBO
                if posRange:
                    finalTp = targetPrice
                elif liqMode:
                    finalTp = tp2Liq
                elif p.exitMode == "runner_trail":
                    finalTp = NA
                else:
                    finalTp = targetPrice
                hasPartial = (not posRange) and (liqMode or (p.exitMode in ("runner", "runner_trail") and posTier >= 2))
                if posRange:
                    tp1Raw = targetPrice
                elif liqMode:
                    tp1Raw = tp1Liq
                elif posTier >= 2:
                    tp1Raw = entryRef + posDir * riskR * p.partialAtR
                else:
                    tp1Raw = bbUp[i] if posDir == 1 else bbLo[i]
                if posDir == 1:
                    tp1Valid = tp1Raw > c[i] and (finalTp != finalTp or tp1Raw < finalTp)
                else:
                    tp1Valid = tp1Raw < c[i] and (finalTp != finalTp or tp1Raw > finalTp)
                tp1Limit = tp1Raw if (hasPartial and tp1Valid) else finalTp
                q0 = initQty if initQty == initQty else (entry_order[1] if entry_order else abs(pos))
                exits = dict(stop=stopPrice, tp2=finalTp,
                             tp1=None if partialDone else (q0 * p.partialPct / 100, tp1Limit))

        if cur is not None:   # cerrar lo abierto al final
            fill(c[-1], abs(pos), "Fin", n - 1)
        self.trades, self.eq = trades, eq_curve
        return self


# ---------------------------------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------------------------------
def metrics(sim, start=None, end=None, capital=10000.0):
    tr = [x for x in sim.trades if (start is None or x.entry_time >= pd.Timestamp(start, tz="UTC"))
          and (end is None or x.entry_time < pd.Timestamp(end, tz="UTC"))]
    pnls = np.array([x.pnl for x in tr]) if tr else np.array([])
    gw = pnls[pnls > 0].sum() if len(pnls) else 0.0
    gl = -pnls[pnls < 0].sum() if len(pnls) else 0.0
    eq = pd.Series(sim.eq, index=sim.t).dropna()
    if start:
        eq = eq[eq.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        eq = eq[eq.index < pd.Timestamp(end, tz="UTC")]
    dd = ((eq.cummax() - eq) / eq.cummax()).max() * 100 if len(eq) else 0.0
    by = {}
    for x in tr:
        b = by.setdefault(x.category, [0, 0, 0.0, 0.0])
        b[0] += 1
        b[1] += x.pnl > 0
        b[2] += max(x.pnl, 0)
        b[3] += -min(x.pnl, 0)
    return dict(trades=len(tr), net=pnls.sum() if len(pnls) else 0.0, netPct=(pnls.sum() / capital * 100) if len(pnls) else 0.0,
                win=(pnls > 0).mean() * 100 if len(pnls) else 0.0, pf=(gw / gl) if gl > 0 else float("inf") if gw > 0 else 0.0,
                maxDD=dd, by=by)
