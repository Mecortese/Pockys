"""Prueba de gatillos de entrada alternativos (misma familia: Bollinger + tendencia HTF + liquidez) con 6 años de datos.

Cada gatillo genera señales al cierre; entrada a la apertura siguiente; stop = extremo de las últimas
5 velas +/- 0.5 ATR (mínimo 1 ATR); se mide qué se toca primero: stop (-1R) u objetivo (+X R).
Resultados netos de comisión, separados por período para ver si la ventaja es estable.
"""
import sys
import numpy as np
import pandas as pd
from engine import Sim, Params

PERIODS = [("2020-06-01", "2022-01-01"), ("2022-01-01", "2023-07-01"), ("2023-07-01", "2025-01-01"), ("2025-01-01", "2026-09-26")]


def load1h(sym):
    """Velas de 1h (Binance / Yahoo)."""
    df = pd.read_csv(f"data/{sym}_1h.csv")
    df.index = pd.to_datetime(df.time, unit="ms", utc=True)
    return df[["open", "high", "low", "close", "volume"]]


def signals(s):
    c, h, l, o = s.c, s.h, s.l, s.o
    H1, H4 = s.H1, s.H4
    mid, up, lo = s.bbMid, s.bbUp, s.bbLo
    pc = np.roll(c, 1)
    trendUp = (H4["tr"] == 1) & (H4["cl"] > H4["mid"]) & (H1["tr"] == 1)
    trendDn = (H4["tr"] == -1) & (H4["cl"] < H4["mid"]) & (H1["tr"] == -1)
    macroUp = (H4["cl"] > H4["mid"])
    macroDn = (H4["cl"] < H4["mid"])
    adxLow = H1["adx"] < 20
    bw1 = H1["up"] - H1["lo"]
    pctB1 = (c - H1["lo"]) / bw1
    newEvt = np.r_[False, s.evcL[1:] != s.evcL[:-1]]
    don_hi = pd.Series(h).rolling(20).max().shift(1).values
    don_lo = pd.Series(l).rolling(20).min().shift(1).values
    sig = {
        "CHOCH_con_tendencia": (newEvt & (s.evL == 2) & trendUp, newEvt & (s.evL == -2) & trendDn),
        "Rebote_media_BB_tendencia": ((l <= mid) & (c > mid) & (pc > mid) & trendUp, (h >= mid) & (c < mid) & (pc < mid) & trendDn),
        "Rechazo_banda_ext_tendencia": ((l <= lo) & (c > lo) & trendUp, (h >= up) & (c < up) & trendDn),
        "Ruptura_banda_BB_tendencia": ((c > up) & (pc <= np.roll(up, 1)) & trendUp, (c < lo) & (pc >= np.roll(lo, 1)) & trendDn),
        "Ruptura_banda_BB_macro": ((c > up) & (pc <= np.roll(up, 1)) & macroUp, (c < lo) & (pc >= np.roll(lo, 1)) & macroDn),
        "Donchian20_macro": ((c > don_hi) & macroUp, (c < don_lo) & macroDn),
        "Reversion_rango_1h": ((pctB1 < 0.15) & adxLow & (c > lo) & (pc <= np.roll(lo, 1)), (pctB1 > 0.85) & adxLow & (c < up) & (pc >= np.roll(up, 1))),
    }
    return sig


def outcomes(s, longs, shorts, targets=(1.0, 2.0, 3.0), comm=0.0004, horizon=200):
    o, h, l, c, atr = s.o, s.h, s.l, s.c, s.atr
    n = len(c)
    lo5 = pd.Series(l).rolling(5).min().values
    hi5 = pd.Series(h).rolling(5).max().values
    rows = []
    last_exit = -1
    for i in range(30, n - 2):
        for d, arr in ((1, longs), (-1, shorts)):
            if not arr[i] or atr[i] != atr[i]:
                continue
            e = o[i + 1]
            sl = min(lo5[i] - 0.5 * atr[i], e - atr[i]) if d == 1 else max(hi5[i] + 0.5 * atr[i], e + atr[i])
            risk = abs(e - sl)
            costR = 2 * comm * e / risk
            res = {}
            for T in targets:
                tg = e + d * T * risk
                r = None
                for j in range(i + 1, min(n, i + horizon)):
                    if (l[j] <= sl) if d == 1 else (h[j] >= sl):
                        r = -1.0
                        break
                    if (h[j] >= tg) if d == 1 else (l[j] <= tg):
                        r = T
                        break
                if r is None:
                    r = d * (c[min(n - 1, i + horizon - 1)] - e) / risk
                res[f"R{T:g}"] = r - costR
            rows.append(dict(time=s.t[i], dir=d, **res))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    tf = sys.argv[1]
    syms = sys.argv[2].split(",")
    out = []
    for sym in syms:
        s = Sim(load1h(sym), tf, Params())
        for name, (L, S) in signals(s).items():
            df = outcomes(s, L, S)
            if df.empty:
                continue
            for a, b in PERIODS:
                x = df[(df.time >= pd.Timestamp(a, tz="UTC")) & (df.time < pd.Timestamp(b, tz="UTC"))]
                out.append(dict(sym=sym, trig=name, per=a[:7], n=len(x), R1=x.R1.mean(), R2=x.R2.mean(), R3=x.R3.mean()))
    r = pd.DataFrame(out)
    r.to_csv(f"results/alt_{tf}.csv", index=False)
    piv = r.pivot_table(index=["trig", "sym"], columns="per", values="R2").round(3)
    print("R medio neto por operación con objetivo 2R, por período:\n", piv.to_string())
    agg = r.assign(w=r.n).groupby("trig").apply(lambda g: pd.Series({"n": g.n.sum(),
            "R1": (g.R1 * g.n).sum() / g.n.sum(), "R2": (g.R2 * g.n).sum() / g.n.sum(), "R3": (g.R3 * g.n).sum() / g.n.sum()}))
    print("\nTotal (todos los activos y períodos):\n", agg.round(3).to_string())
