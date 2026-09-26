"""Objetivo del usuario: entrar en 5m y que el precio llegue a +1R (para mover el SL a la entrada) antes del stop.

Para cada gatillo de 5m y cada contexto HTF mide:
  P(+1R antes que -1R)  -> % de entradas donde se puede poner el SL en la entrada
  P(+2R / +3R antes que -1R)
  MFE mediano (máximo avance a favor en R dentro de 1 día)
Stop = extremo de las últimas 10 velas +/- 0.3 ATR (mínimo por comisión), entrada a la apertura siguiente.
"""
import sys
import numpy as np
import pandas as pd
from engine import Sim, Params, bollinger, market_structure
from run import load


def daily_trend(df5, idx):
    d = df5.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    c = d.close.values
    s50 = pd.Series(c).rolling(50).mean().values
    tr, *_ = market_structure(d.high.values, d.low.values, c, 3)
    feat = pd.DataFrame({"dUp": (c > s50).astype(int) - (c < s50).astype(int), "dTr": tr}, index=d.index).shift(1)  # día cerrado
    return feat.reindex(idx.floor("D")).set_index(idx)


def run(sym):
    df5 = load(sym)
    s = Sim(df5, "5", Params())
    o, h, l, c, atr, t = s.o, s.h, s.l, s.c, s.atr, s.t
    H1, H4 = s.H1, s.H4
    D = daily_trend(df5, t)
    n = len(c)
    lo10 = pd.Series(l).rolling(10).min().values
    hi10 = pd.Series(h).rolling(10).max().values
    newEvt = np.r_[False, s.evcL[1:] != s.evcL[:-1]]
    pc = np.roll(c, 1)
    mid, up, lo = s.bbMid, s.bbUp, s.bbLo
    trig = {
        "CHOCH 5m": (newEvt & (s.evL == 2), newEvt & (s.evL == -2)),
        "Ruptura BB 5m": ((c > up) & (pc <= np.roll(up, 1)), (c < lo) & (pc >= np.roll(lo, 1))),
        "Rebote media BB 5m": ((l <= mid) & (c > mid) & (pc > np.roll(mid, 1)), (h >= mid) & (c < mid) & (pc < np.roll(mid, 1))),
    }
    start = pd.Timestamp("2025-09-25", tz="UTC")
    rows = []
    for name, (L, S) in trig.items():
        for i in range(300, n - 300):
            if t[i] < start or atr[i] != atr[i]:
                continue
            for d, arr in ((1, L), (-1, S)):
                if not arr[i]:
                    continue
                e = o[i + 1]
                minD = max(0.5 * atr[i], 4 * 2 * 0.0004 * e)
                sl = min(lo10[i] - 0.3 * atr[i], e - minD) if d == 1 else max(hi10[i] + 0.3 * atr[i], e + minD)
                risk = abs(e - sl)
                hit = {1: 0, 2: 0, 3: 0}
                mfe = 0.0
                for j in range(i + 1, min(n, i + 288)):
                    adv = (h[j] - e) / risk if d == 1 else (e - l[j]) / risk
                    stopped = (l[j] <= sl) if d == 1 else (h[j] >= sl)
                    if stopped:
                        break                       # conservador: si en la misma vela toca stop, cuenta stop
                    mfe = max(mfe, adv)
                    for k in hit:
                        if not hit[k] and adv >= k:
                            hit[k] = 1
                al1 = int(H1["tr"][i] == d)
                al4 = int(H4["tr"][i] == d and ((H4["cl"][i] > H4["mid"][i]) == (d == 1)))
                alD = int(D["dUp"].iloc[i] == d and D["dTr"].iloc[i] == d)
                rows.append(dict(trig=name, dir=d, h1=hit[1], h2=hit[2], h3=hit[3], mfe=mfe, al1=al1, al4=al4, alD=alD,
                                 costR=2 * 0.0004 * e / risk))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = pd.concat([run(s).assign(sym=s) for s in sys.argv[1].split(",")])
    df.to_csv("results/be5.csv", index=False)
    df["ctx"] = np.select([(df.alD == 1) & (df.al4 == 1) & (df.al1 == 1), (df.al4 == 1) & (df.al1 == 1), (df.al1 == 1)],
                          ["D+4h+1h a favor", "4h+1h a favor", "solo 1h a favor"], "sin respaldo")
    g = df.groupby(["trig", "ctx"]).agg(n=("h1", "size"), llega_1R=("h1", "mean"), llega_2R=("h2", "mean"),
                                         llega_3R=("h3", "mean"), MFE_med=("mfe", "median"))
    g[["llega_1R", "llega_2R", "llega_3R"]] *= 100
    print(g.round(1).to_string())
