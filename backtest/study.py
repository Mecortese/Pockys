"""Compara variantes de la estrategia: in-sample (8 meses) para elegir, out-of-sample (4 meses) para validar."""
import sys, itertools, json
from dataclasses import replace
from multiprocessing import Pool
import pandas as pd
from engine import Sim, Params, metrics
from run import load
from alt import load1h

import os
IS = tuple(os.environ.get("IS", "2025-09-25,2026-05-25").split(","))
OOS = tuple(os.environ.get("OOS", "2026-05-25,2026-09-26").split(","))
FULL = tuple(os.environ.get("FULL", "2025-09-25,2026-09-26").split(","))
_cache = {}

def job(args):
    sym, tf, name, kw = args
    if sym not in _cache:
        _cache[sym] = load(sym) if tf in ("5", "15") else load1h(sym)
    p = replace(Params(), **kw)
    s = Sim(_cache[sym], tf, p, FULL[0], FULL[1]).run()
    out = {"sym": sym, "tf": tf, "var": name}
    for tag, (a, b) in (("is", IS), ("oos", OOS), ("full", FULL)):
        m = metrics(s, a, b, p.initialCapital)
        out.update({f"{tag}_n": m["trades"], f"{tag}_net": round(m["netPct"], 2), f"{tag}_pf": round(min(m["pf"], 99), 2),
                    f"{tag}_win": round(m["win"], 1), f"{tag}_dd": round(m["maxDD"], 2)})
    out["by"] = {k: [v[0], round(v[2] - v[3], 1)] for k, v in metrics(s, *FULL, p.initialCapital)["by"].items()}
    return out

BO = {"useBreakout": True, "usePullback": False, "useScalp": False, "useRangeMode": False}
SQ = {"useSqueeze": True, "usePullback": False, "useScalp": False, "useRangeMode": False, "exitMode": "fixed", "moveToBE": False, "closeOnChoch": False}
RS = {"useRS": True, "usePullback": False, "useScalp": False, "useRangeMode": False}
VARIANTS = {
    "squeeze_3R": SQ,
    "squeeze_2R": {**SQ, "rrBreakout": 2.0},
    "squeeze_3R_macro": {**SQ, "sqzTrend": True},
    "rs_base": RS,
    "liq4h_3R": {**RS, "rsMode": "htfpullback", "moveToBE": False},
    "liq4h_2R": {**RS, "rsMode": "htfpullback", "moveToBE": False, "rsTargetR": 2.0},
    "rs_trend_sinBE": {**RS, "moveToBE": False},
    "G_adapt": {**RS, "moveToBE": False, "commSim": 0.0, "rsAdaptive": True},
    "G_adapt_1.5": {**RS, "moveToBE": False, "commSim": 0.0, "rsAdaptive": True, "rsScalpR": 1.5},
    "G_trend_3R": {**RS, "moveToBE": False, "commSim": 0.0},
    "G_trend_1R": {**RS, "moveToBE": False, "commSim": 0.0, "rsTargetR": 1.0},
    "G_trend_1.5R": {**RS, "moveToBE": False, "commSim": 0.0, "rsTargetR": 1.5},
    "G_h1_1R": {**RS, "rsMode": "h1", "moveToBE": False, "commSim": 0.0, "rsTargetR": 1.0},
    "G_h1_1.5R": {**RS, "rsMode": "h1", "moveToBE": False, "commSim": 0.0, "rsTargetR": 1.5},
    "G_h1_3R": {**RS, "rsMode": "h1", "moveToBE": False, "commSim": 0.0},
    "G_libre_1R": {**RS, "rsMode": "none", "moveToBE": False, "commSim": 0.0, "rsTargetR": 1.0},
    "G_liq4h_1R": {**RS, "rsMode": "htfpullback", "moveToBE": False, "commSim": 0.0, "rsTargetR": 1.0},
    "scalp_trend_1R": {**RS, "moveToBE": False, "rsTargetR": 1.0},
    "scalp_trend_1.5R": {**RS, "moveToBE": False, "rsTargetR": 1.5},
    "scalp_liq4h_1R": {**RS, "rsMode": "htfpullback", "moveToBE": False, "rsTargetR": 1.0},
    "scalp_liq4h_1.5R": {**RS, "rsMode": "htfpullback", "moveToBE": False, "rsTargetR": 1.5},
    "rs_BE1.5": {**RS, "rsBeR": 1.5},
    "rs_sinBE": {**RS, "moveToBE": False},
    "rs_2R": {**RS, "rsTargetR": 2.0},
    "rs_2R_sinBE": {**RS, "rsTargetR": 2.0, "moveToBE": False},
    "rs_sin_anticipo": {**RS, "rsAntic": False},
    "rs_cost_maker": {**RS, "commSim": 0.02},
    "rs_BE2": {**RS, "rsBeR": 2.0},
    "ruptura_3R": {**BO, "exitMode": "fixed"},
    "ruptura_3R_sinCHOCH": {**BO, "exitMode": "fixed", "closeOnChoch": False},
    "ruptura_3R_sinBE": {**BO, "exitMode": "fixed", "moveToBE": False},
    "ruptura_3R_sinBE_sinCHOCH": {**BO, "exitMode": "fixed", "moveToBE": False, "closeOnChoch": False},
    "ruptura_parcial_trail": {**BO, "exitMode": "runner_trail", "partialAtR": 2.0, "moveToBE": False, "closeOnChoch": False},
    "ruptura_macro_3R_sinBE_sinCHOCH": {**BO, "breakoutTrendMode": "macro", "exitMode": "fixed", "moveToBE": False, "closeOnChoch": False},
    "ruptura_4R_sinBE_sinCHOCH": {**BO, "exitMode": "fixed", "rrBreakout": 4.0, "moveToBE": False, "closeOnChoch": False},
    "base": {},
    "base_sin_comision": {"commSim": 0.0},
    "sin_comision_sin_recorrido": {"commSim": 0.0, "useRoomFilter": False},
    "sin_filtro_recorrido": {"useRoomFilter": False},
    "recorrido_1.5R": {"minRoomR": 1.5},
    "salida_TP_fijo": {"exitMode": "fixed"},
    "todos_los_tipos": {"minTier": 1},
    "sin_modo_rango": {"useRangeMode": False},
    "sin_ADX": {"useAdxFilter": False},
    "solo_pullback": {"useScalp": False, "useRangeMode": False},
    "solo_CHOCH": {"usePullback": False, "useRangeMode": False},
    "solo_rango": {"usePullback": False, "useScalp": False},
    "sin_cierre_CHOCH_1h": {"closeOnChoch": False},
    "sin_breakeven": {"moveToBE": False},
}

if __name__ == "__main__":
    syms = sys.argv[1].split(",")
    tfs = sys.argv[2].split(",")
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else list(VARIANTS)
    jobs = [(s, t, n, VARIANTS[n]) for s in syms for t in tfs for n in names]
    with Pool(int(sys.argv[4]) if len(sys.argv) > 4 else 4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    df = pd.DataFrame(res)
    df.to_json(f"results/study_{'_'.join(syms)}_{'_'.join(tfs)}.json", orient="records")
    cols = ["sym", "tf", "var", "is_n", "is_net", "is_pf", "oos_n", "oos_net", "oos_pf", "full_net", "full_pf", "full_win", "full_dd"]
    print(df[cols].to_string(index=False))
