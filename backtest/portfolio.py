"""Cartera BTC + Oro + Nasdaq con filtro de tendencia diario (solo compra) y pesos por volatilidad.

Pesos: 1/3 fijo o inversos a la volatilidad de 60 días (paridad de riesgo). Filtro por activo: estar invertido sólo
si la tendencia es alcista (media 200 / cruce 50-200 / momentum 12m). Rebalanceo semanal. Costos incluidos.
"""
import numpy as np
import pandas as pd
from classic import load, COST

names = ["BTC", "GOLD", "NDX"]
dfs = {n: load(n) for n in names}
idx = dfs["BTC"].index.union(dfs["GOLD"].index).union(dfs["NDX"].index)
start = pd.Timestamp("2015-12-14")
idx = idx[idx >= pd.Timestamp("2014-09-17")]

def filt(df, kind):
    c = df.close
    if kind == "sma200":
        return (c > c.rolling(200).mean())
    if kind == "cruce50200":
        return (c.rolling(50).mean() > c.rolling(200).mean())
    if kind == "mom12":
        return (c / c.shift(252) - 1) > 0
    if kind == "ninguno":
        return pd.Series(True, index=c.index)
    if kind == "voto":   # 2 de 3 filtros
        return (filt(df, "sma200").astype(int) + filt(df, "cruce50200").astype(int) + filt(df, "mom12").astype(int)) >= 2

def run(kind, weighting, target_vol=None, rebal="W-FRI"):
    rets, sig, vol = {}, {}, {}
    for n, df in dfs.items():
        o = df.open.reindex(idx).ffill()
        r = (o.shift(-2) / o.shift(-1) - 1).fillna(0)
        # los días sin mercado (fines de semana en oro/nasdaq) tienen retorno 0
        rets[n] = r.where(df.open.reindex(idx).notna(), 0.0)
        sig[n] = filt(df, kind).reindex(idx).ffill().fillna(False).astype(float)
        vol[n] = df.close.pct_change().rolling(60).std().reindex(idx).ffill() * np.sqrt(252)
    R, SIG, VOL = pd.DataFrame(rets), pd.DataFrame(sig), pd.DataFrame(vol)
    if weighting == "igual":
        W = pd.DataFrame(1 / 3, index=idx, columns=names)
    else:
        iv = 1 / VOL
        W = iv.div(iv.sum(axis=1), axis=0)
    W = W * SIG
    if target_vol:
        # escala para apuntar a una volatilidad anual objetivo (máx. 1.5x)
        port_vol = (W * VOL).pow(2).sum(axis=1).pow(0.5)       # aproximación sin correlaciones
        W = W.mul((target_vol / port_vol).clip(upper=1.5 / W.sum(axis=1).replace(0, np.nan)).fillna(0), axis=0)
    W = W.resample(rebal).last().reindex(idx).ffill().fillna(0)
    turn = W.diff().abs().fillna(W.abs())
    cost = sum(turn[n] * COST[n] for n in names)
    pr = (W * R).sum(axis=1) - cost
    pr = pr[pr.index >= start]
    eq = (1 + pr).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (1 - eq / eq.cummax()).max()
    sh = pr.mean() / pr.std() * np.sqrt(365)
    yearly = (1 + pr).groupby(pr.index.year).prod() - 1
    return dict(CAGR=round(cagr * 100, 1), MaxDD=round(dd * 100, 1), Sharpe=round(sh, 2), MAR=round(cagr / dd, 2),
                peor_año=round(yearly.min() * 100, 1), años_negativos=int((yearly < 0).sum())), yearly

if __name__ == "__main__":
    rows, yearly = {}, {}
    for kind in ("ninguno", "sma200", "cruce50200", "mom12", "voto"):
        for w in ("igual", "paridad_riesgo"):
            rows[f"{kind} · {w}"], yearly[f"{kind} · {w}"] = run(kind, w)
    rows["voto · paridad_riesgo · vol 20%"], yearly["voto · paridad_riesgo · vol 20%"] = run("voto", "paridad_riesgo", 0.20)
    print(pd.DataFrame(rows).T.to_string())
    print("\nRetorno por año (%):")
    print((pd.DataFrame(yearly)[["ninguno · igual", "voto · igual", "voto · paridad_riesgo", "voto · paridad_riesgo · vol 20%"]] * 100).round(1).to_string())
