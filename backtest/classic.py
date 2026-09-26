"""Estrategias clásicas y publicadas, en velas diarias, sin optimizar (reglas tal cual se publicaron).

Señal al cierre del día t -> posición desde la apertura de t+1. Costos por cambio de posición.
Métricas: CAGR, caída máxima, Sharpe, % de tiempo invertido, nº de operaciones; comparación con comprar y mantener.
"""
import sys
import numpy as np
import pandas as pd

COST = {"BTC": 0.0010, "GOLD": 0.0003, "NDX": 0.0003}     # por lado (comisión + deslizamiento)
ANN = {"BTC": 365, "GOLD": 252, "NDX": 252}


def load(name):
    df = pd.read_csv(f"data/{name}_1d.csv")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.time, unit="ms")).normalize()
    return df[["open", "high", "low", "close"]]


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def stateful(entry_long, exit_long, entry_short=None, exit_short=None):
    """Posición con entradas/salidas (1, 0, -1)."""
    pos = np.zeros(len(entry_long))
    p = 0
    el, xl = entry_long.values, exit_long.values
    es = entry_short.values if entry_short is not None else np.zeros(len(el), bool)
    xs = exit_short.values if exit_short is not None else np.zeros(len(el), bool)
    for i in range(len(el)):
        if p == 1 and xl[i]:
            p = 0
        elif p == -1 and xs[i]:
            p = 0
        if p == 0:
            if el[i]:
                p = 1
            elif es[i]:
                p = -1
        pos[i] = p
    return pd.Series(pos, index=entry_long.index)


def strategies(df):
    c, h, l = df.close, df.high, df.low
    sma200, sma50, sma5 = c.rolling(200).mean(), c.rolling(50).mean(), c.rolling(5).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    up, lo = mid + 2 * sd, mid - 2 * sd
    hh55, ll20 = h.rolling(55).max().shift(1), l.rolling(20).min().shift(1)
    ll55, hh20 = l.rolling(55).min().shift(1), h.rolling(20).max().shift(1)
    r2 = rsi(c, 2)
    mom = c / c.shift(252) - 1
    S = {}
    S["Comprar y mantener"] = pd.Series(1.0, index=c.index)
    S["Faber: sobre media 200 (solo compra)"] = (c > sma200).astype(float)
    S["Cruce medias 50/200 (solo compra)"] = (sma50 > sma200).astype(float)
    S["Momentum 12 meses (solo compra)"] = (mom > 0).astype(float)
    S["Turtle 55/20 (solo compra)"] = stateful(c > hh55, c < ll20)
    S["Turtle 55/20 (compra y venta)"] = stateful(c > hh55, c < ll20, c < ll55, c > hh20)
    S["Ruptura BB diaria + media 200 (solo compra)"] = stateful((c > up) & (c > sma200), c < mid)
    S["Connors RSI2 (solo compra)"] = stateful((c > sma200) & (r2 < 10), c > sma5)
    # combinación: tendencia (Faber) + reversión RSI2, mitad del capital en cada una
    S["Combo 50% Faber + 50% RSI2"] = 0.5 * S["Faber: sobre media 200 (solo compra)"] + 0.5 * S["Connors RSI2 (solo compra)"]
    return S


def evaluate(df, pos, cost, ann):
    o = df.open
    ret = (o.shift(-2) / o.shift(-1) - 1).fillna(0)          # retorno de apertura t+1 a apertura t+2
    turn = pos.diff().abs().fillna(pos.abs())
    strat = pos * ret - turn * cost
    eq = (1 + strat).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (1 - eq / eq.cummax()).max()
    sharpe = strat.mean() / strat.std() * np.sqrt(ann) if strat.std() > 0 else 0
    trades = int((pos.diff().fillna(0) != 0).sum() / 2)
    return dict(CAGR=cagr * 100, MaxDD=dd * 100, Sharpe=sharpe, Expo=(pos != 0).mean() * 100, Ops=trades,
                MAR=(cagr / dd) if dd > 0 else 0)


if __name__ == "__main__":
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else ["BTC", "GOLD", "NDX"]
    for name in names:
        df = load(name)
        S = strategies(df)
        first = df.index[200 + 252]          # descartar calentamiento de indicadores
        d = df[df.index >= first]
        rows = {}
        for k, pos in S.items():
            rows[k] = evaluate(d, pos[pos.index >= first], COST[name], ANN[name])
        print(f"\n===== {name}  ({d.index[0].date()} → {d.index[-1].date()}) =====")
        print(pd.DataFrame(rows).T.round(2).to_string())
        # estabilidad por subperíodos
        edges = pd.date_range(d.index[0], d.index[-1], periods=4)
        per = {}
        for a, b in zip(edges[:-1], edges[1:]):
            dd_ = d[(d.index >= a) & (d.index < b)]
            per[f"{a.year}-{b.year}"] = {k: round(evaluate(dd_, S[k][(S[k].index >= a) & (S[k].index < b)], COST[name], ANN[name])["CAGR"], 1) for k in S}
        print("\nCAGR % por subperíodo:")
        print(pd.DataFrame(per).to_string())
