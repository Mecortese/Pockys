"""Motor 'Respaldo D+HTF' en varios timeframes (misma lógica que el Pine por defecto).

Gatillos: liquidez + CHOCH a favor (toque de banda BB o barrido de mínimo/máximo en las últimas 15 velas) o
ruptura de banda BB, sólo con Diario + macro + confirmación a favor. Gestión: SL a la entrada en +1R, objetivo 3R.
"""
import sys
import numpy as np
import pandas as pd
from engine import Sim, Params
from run import load
from alt import load1h
from be5 import daily_trend

def run(sym, tf, start, end):
    df = load(sym) if tf in ("5", "15") else load1h(sym)
    s = Sim(df, tf, Params())
    o, h, l, c, atr, t = s.o, s.h, s.l, s.c, s.atr, s.t
    H1, H4 = s.H1, s.H4
    D = daily_trend(df, t)
    n = len(c)
    lo10 = pd.Series(l).rolling(10).min().values
    hi10 = pd.Series(h).rolling(10).max().values
    prevLo = pd.Series(l).rolling(20).min().shift(1).values
    prevHi = pd.Series(h).rolling(20).max().shift(1).values
    liqB = (l <= s.bbLo) | ((l < prevLo) & (c > prevLo))
    liqS = (h >= s.bbUp) | ((h > prevHi) & (c < prevHi))
    liqBok = pd.Series(liqB.astype(float)).rolling(15, min_periods=1).max().values > 0
    liqSok = pd.Series(liqS.astype(float)).rolling(15, min_periods=1).max().values > 0
    newEvt = np.r_[False, s.evcL[1:] != s.evcL[:-1]]
    pc = np.roll(c, 1)
    chL, chS = newEvt & (s.evL == 2) & liqBok, newEvt & (s.evL == -2) & liqSok
    bbL = (c > s.bbUp) & (pc <= np.roll(s.bbUp, 1))
    bbS = (c < s.bbLo) & (pc >= np.roll(s.bbLo, 1))
    dUp, dTr = D["dUp"].values, D["dTr"].values
    resp = lambda i, d: dUp[i] == d and dTr[i] == d and H4["tr"][i] == d and ((H4["cl"][i] > H4["mid"][i]) == (d == 1)) and H1["tr"][i] == d
    a, b = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    rows = []
    for i in range(300, n - 2):
        if t[i] < a or t[i] >= b or atr[i] != atr[i]:
            continue
        for d, CH, BB in ((1, chL, bbL), (-1, chS, bbS)):
            if not (CH[i] or BB[i]):
                continue
            e = o[i + 1]
            minD = max(0.5 * atr[i], 4 * 2 * 0.0004 * e)
            sl = min(lo10[i] - 0.3 * atr[i], e - minD) if d == 1 else max(hi10[i] + 0.3 * atr[i], e + minD)
            risk = abs(e - sl)
            h1 = h3 = 0
            for j in range(i + 1, min(n, i + 288)):
                if (l[j] <= sl) if d == 1 else (h[j] >= sl):
                    break
                adv = (h[j] - e) / risk if d == 1 else (e - l[j]) / risk
                h1 = h1 or adv >= 1
                if adv >= 3:
                    h3 = 1
                    break
            R = (3 if h3 else 0 if h1 else -1) - 2 * 0.0004 * e / risk
            rows.append(dict(time=t[i], sym=sym, tf=tf, trig="CHOCH+liq" if CH[i] else "Ruptura BB", resp=resp(i, d), h1=int(bool(h1)), R=R))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    out = []
    for tf in ("5", "15", "60", "240"):
        for sym in ("BTCUSDT", "ETHUSDT"):
            out.append(run(sym, tf, "2025-09-25", "2026-09-26").assign(per="último año"))
            if tf in ("60", "240"):
                out.append(run(sym, tf, "2020-06-01", "2025-09-25").assign(per="2020-2025"))
    df = pd.concat(out)
    df.to_csv("results/be_tf.csv", index=False)
    months = {"último año": 12, "2020-2025": 63.8}
    g = df.groupby(["per", "tf", "resp"]).agg(ops=("R", "size"), llega_1R=("h1", "mean"), R_medio=("R", "mean"), R_total=("R", "sum"))
    g["ops_mes_x_activo"] = g.ops / g.index.get_level_values(0).map(months) / 2
    g["llega_1R"] *= 100
    print(g.round(2).to_string())
    print("\nCon respaldo, por activo y gatillo (último año):")
    x = df[(df.resp) & (df.per == "último año")]
    print(x.groupby(["tf", "sym", "trig"]).R.agg(["count", "mean"]).round(3).to_string())
