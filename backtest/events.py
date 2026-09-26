"""Estudio de eventos: ¿qué contextos le dan ventaja a un CHOCH del gráfico?

Para cada CHOCH (alcista -> compra, bajista -> venta) se simula una operación estándar:
  stop = extremo de las últimas N velas +/- colchón ATR (ampliado al riesgo mínimo por comisión)
  objetivo = +R_TARGET R;  se mira qué se toca primero (stop u objetivo) en las velas siguientes.
Resultado en R neto de comisión. Luego se agrupa por características del contexto.
"""
import sys
import numpy as np
import pandas as pd
from engine import Sim, Params
from run import load

R_TARGET = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
HORIZON = 300


def study(sym, tf, p=Params()):
    s = Sim(load(sym), tf, p)
    o, h, l, c, atr = s.o, s.h, s.l, s.c, s.atr
    H1, H4 = s.H1, s.H4
    n = len(c)
    rows = []
    evc = s.evcL
    lowest = pd.Series(l).rolling(p.scalpSlLookback, min_periods=1).min().values
    highest = pd.Series(h).rolling(p.scalpSlLookback, min_periods=1).max().values
    # barras desde el último toque de banda / zona extrema 1h / barrido
    bbLo, bbUp = s.bbLo, s.bbUp
    last_lo = last_up = -10 ** 9
    last_sw_lo = last_sw_hi = -10 ** 9
    swH = swL = np.nan
    for i in range(1, n - 1):
        if l[i] <= bbLo[i]:
            last_lo = i
        if h[i] >= bbUp[i]:
            last_up = i
        if s.phL[i] == s.phL[i]:
            swH = s.phL[i]
        if s.plL[i] == s.plL[i]:
            swL = s.plL[i]
        if swL == swL and l[i] < swL < c[i]:
            last_sw_lo, swL = i, np.nan
        if swH == swH and h[i] > swH > c[i]:
            last_sw_hi, swH = i, np.nan
        if evc[i] == evc[i - 1] or abs(s.evL[i]) != 2 or atr[i] != atr[i] or H1["up"][i] != H1["up"][i] or H4["up"][i] != H4["up"][i]:
            continue
        d = 1 if s.evL[i] == 2 else -1
        px = c[i]
        a = atr[i]
        minD = max(p.minRiskAtr * a, p.minRiskCost * 2 * p.commPct / 100 * px)
        sl = min(lowest[i] - p.scalpSlAtrBuf * a, px - minD) if d == 1 else max(highest[i] + p.scalpSlAtrBuf * a, px + minD)
        entry = o[i + 1]
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tgt = entry + d * R_TARGET * risk
        res = None
        for j in range(i + 1, min(n, i + HORIZON)):
            hit_sl = l[j] <= sl if d == 1 else h[j] >= sl
            hit_tp = h[j] >= tgt if d == 1 else l[j] <= tgt
            if hit_sl:          # conservador: si ambos en la misma vela, cuenta el stop
                res = -1.0
                break
            if hit_tp:
                res = R_TARGET
                break
        if res is None:
            res = d * (c[min(n - 1, i + HORIZON - 1)] - entry) / risk
        costR = 2 * p.commPct / 100 * entry / risk
        bw1 = H1["up"][i] - H1["lo"][i]
        bw4 = H4["up"][i] - H4["lo"][i]
        pctB1 = (px - H1["lo"][i]) / bw1 if bw1 > 0 else np.nan
        pctB4 = (px - H4["lo"][i]) / bw4 if bw4 > 0 else np.nan
        nl = s.next_level(i, px, d, 0.0)
        room = abs(nl - px) / risk if nl == nl else 99.0
        rows.append(dict(
            time=s.t[i], dir=d, R=res - costR, Rgross=res,
            # contexto expresado "a favor de la operación"
            al1=int(H1["tr"][i] == d), al4=int(H4["tr"][i] == d),
            basis4=int((H4["cl"][i] > H4["mid"][i]) == (d == 1)),
            pctB1=pctB1 if d == 1 else 1 - pctB1,      # 0 = extremo favorable (compra abajo / venta arriba)
            pctB4=pctB4 if d == 1 else 1 - pctB4,
            adx1=H1["adx"][i], room=room,
            bandTouch=int((i - (last_lo if d == 1 else last_up)) <= 20),
            sweep=int((i - (last_sw_lo if d == 1 else last_sw_hi)) <= 15),
            riskAtr=risk / a,
        ))
    return pd.DataFrame(rows)


def summarize(df, col, bins=None):
    g = df.groupby(pd.cut(df[col], bins) if bins is not None else df[col], observed=True)["R"]
    return g.agg(["count", "mean", lambda x: (x > 0).mean()]).rename(columns={"<lambda_0>": "win"})


if __name__ == "__main__":
    sym, tf = sys.argv[1], sys.argv[2]
    df = study(sym, tf)
    df.to_csv(f"results/events_{sym}_{tf}.csv", index=False)
    print(f"{sym} {tf}: eventos={len(df)}  R medio neto={df.R.mean():.3f}  bruto={df.Rgross.mean():.3f}")
    for col, bins in (("al1", None), ("al4", None), ("basis4", None), ("bandTouch", None), ("sweep", None),
                      ("pctB1", [-9, 0.2, 0.4, 0.6, 0.8, 9]), ("pctB4", [-9, 0.2, 0.4, 0.6, 0.8, 9]),
                      ("adx1", [0, 15, 20, 25, 35, 100]), ("room", [0, 1, 2, 3, 5, 100]), ("riskAtr", [0, 1, 2, 3, 5, 50])):
        print(f"\n-- {col}")
        print(summarize(df, col, bins).round(3).to_string())
