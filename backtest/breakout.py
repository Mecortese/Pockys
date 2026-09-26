"""Ruptura de banda BB a favor de la tendencia (4h): comparación de salidas y filtros de contexto.

Salidas (todas con stop inicial = extremo 5 velas -/+ 0.5 ATR, mínimo 1 ATR):
  fijo2R / fijo3R          : objetivo fijo
  trail3ATR                : trailing (máximo desde la entrada - 3 ATR), activo desde el inicio
  media_BB                 : cierre del lado contrario de la media BB del gráfico
  parcial2R_trail          : 50% en 2R, stop a breakeven y resto con trailing 3 ATR
Filtros evaluados (sin optimizar, se agrupan): recorrido hasta la zona de liquidez HTF en R, %B de la banda diaria, ADX.
"""
import sys
import numpy as np
import pandas as pd
from engine import Sim, Params
from alt import load1h, PERIODS

COMM = 0.0004


def events(s, mode="tendencia"):
    c, H1, H4 = s.c, s.H1, s.H4
    up, lo = s.bbUp, s.bbLo
    pc = np.roll(c, 1)
    if mode == "tendencia":
        tU = (H4["tr"] == 1) & (H4["cl"] > H4["mid"]) & (H1["tr"] == 1)
        tD = (H4["tr"] == -1) & (H4["cl"] < H4["mid"]) & (H1["tr"] == -1)
    else:
        tU, tD = H4["cl"] > H4["mid"], H4["cl"] < H4["mid"]
    L = (c > up) & (pc <= np.roll(up, 1)) & tU
    S = (c < lo) & (pc >= np.roll(lo, 1)) & tD
    return L, S


def simulate(s, L, S, horizon=400):
    o, h, l, c, atr, mid = s.o, s.h, s.l, s.c, s.atr, s.bbMid
    n = len(c)
    lo5 = pd.Series(l).rolling(5).min().values
    hi5 = pd.Series(h).rolling(5).max().values
    rows = []
    for i in range(30, n - 2):
        for d, arr in ((1, L), (-1, S)):
            if not arr[i] or atr[i] != atr[i]:
                continue
            e = o[i + 1]
            sl0 = min(lo5[i] - 0.5 * atr[i], e - atr[i]) if d == 1 else max(hi5[i] + 0.5 * atr[i], e + atr[i])
            risk = abs(e - sl0)
            costR = 2 * COMM * e / risk
            res = {}
            # objetivos fijos
            for T in (2.0, 3.0):
                tg, r = e + d * T * risk, None
                for j in range(i + 1, min(n, i + horizon)):
                    if (l[j] <= sl0) if d == 1 else (h[j] >= sl0):
                        r = -1.0; break
                    if (h[j] >= tg) if d == 1 else (l[j] <= tg):
                        r = T; break
                res[f"fijo{T:g}R"] = (r if r is not None else d * (c[min(n - 1, i + horizon - 1)] - e) / risk) - costR
            # trailing 3 ATR
            st, ext, r = sl0, e, None
            for j in range(i + 1, min(n, i + horizon)):
                if (l[j] <= st) if d == 1 else (h[j] >= st):
                    r = d * (st - e) / risk; break
                ext = max(ext, h[j]) if d == 1 else min(ext, l[j])
                st = max(st, ext - 3 * atr[j]) if d == 1 else min(st, ext + 3 * atr[j])
            res["trail3ATR"] = (r if r is not None else d * (c[min(n - 1, i + horizon - 1)] - e) / risk) - costR
            # salida por media BB
            r = None
            for j in range(i + 1, min(n, i + horizon)):
                if (l[j] <= sl0) if d == 1 else (h[j] >= sl0):
                    r = -1.0; break
                if (c[j] < mid[j]) if d == 1 else (c[j] > mid[j]):
                    r = d * (o[j + 1] - e) / risk if j + 1 < n else d * (c[j] - e) / risk; break
            res["media_BB"] = (r if r is not None else d * (c[min(n - 1, i + horizon - 1)] - e) / risk) - costR
            # parcial 2R + trailing
            st, ext, part, r = sl0, e, 0.0, None
            for j in range(i + 1, min(n, i + horizon)):
                if (l[j] <= st) if d == 1 else (h[j] >= st):
                    r = part + (0.5 if part else 1.0) * d * (st - e) / risk; break
                if not part and ((h[j] >= e + 2 * risk) if d == 1 else (l[j] <= e - 2 * risk)):
                    part = 1.0          # 50% x 2R
                    st = max(st, e) if d == 1 else min(st, e)
                ext = max(ext, h[j]) if d == 1 else min(ext, l[j])
                if part:
                    st = max(st, ext - 3 * atr[j]) if d == 1 else min(st, ext + 3 * atr[j])
            if r is None:
                r = part + (0.5 if part else 1.0) * d * (c[min(n - 1, i + horizon - 1)] - e) / risk
            res["parcial2R_trail"] = r - costR
            # contexto
            nl = s.next_level(i, c[i], d, 0.0)
            bwD = s.H4["up"][i] - s.H4["lo"][i]
            pctBD = (c[i] - s.H4["lo"][i]) / bwD if bwD > 0 else np.nan
            rows.append(dict(time=s.t[i], dir=d, room=abs(nl - c[i]) / risk if nl == nl else 99.0,
                             pctBM=pctBD if d == 1 else 1 - pctBD, adx=s.H1["adx"][i], **res))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    tf = sys.argv[1]
    mode = sys.argv[2]
    syms = sys.argv[3].split(",")
    allr = []
    for sym in syms:
        s = Sim(load1h(sym), tf, Params())
        L, S = events(s, mode)
        df = simulate(s, L, S)
        df["sym"] = sym
        allr.append(df)
    df = pd.concat(allr)
    df.to_csv(f"results/breakout_{tf}_{mode}.csv", index=False)
    ex = ["fijo2R", "fijo3R", "trail3ATR", "media_BB", "parcial2R_trail"]
    print(f"== {tf} {mode}: operaciones={len(df)}")
    print(df.groupby("sym")[ex].mean().round(3).to_string())
    print("\nTOTAL", df[ex].mean().round(3).to_dict())
    df["per"] = pd.cut(df.time, [pd.Timestamp(a, tz="UTC") for a, _ in PERIODS] + [pd.Timestamp(PERIODS[-1][1], tz="UTC")], labels=[a[:7] for a, _ in PERIODS])
    print("\npor período:\n", df.groupby("per", observed=True)[ex].mean().round(3).to_string())
    for col, bins in (("room", [0, 1, 2, 3, 5, 1000]), ("pctBM", [-9, 0.5, 0.8, 1.0, 1.2, 9]), ("adx", [0, 20, 25, 35, 100])):
        print(f"\n-- {col}")
        print(df.groupby(pd.cut(df[col], bins), observed=True)[["trail3ATR", "fijo3R"]].agg(["count", "mean"]).round(3).to_string())
