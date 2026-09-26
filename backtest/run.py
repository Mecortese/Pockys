import sys, time
import pandas as pd
from engine import Sim, Params, metrics

def load(sym):
    df = pd.read_csv(f"data/{sym}_5m.csv")
    df.index = pd.to_datetime(df.time, unit="ms", utc=True)
    return df[["open", "high", "low", "close", "volume"]]

START, END = "2025-09-25", "2026-09-26"

def run(sym, tf, p=None, start=START, end=END, df=None):
    df = load(sym) if df is None else df
    s = Sim(df, tf, p or Params(), start, end).run()
    return s, metrics(s, start, end, (p or Params()).initialCapital)

if __name__ == "__main__":
    sym, tf = sys.argv[1], sys.argv[2]
    t0 = time.time()
    s, m = run(sym, tf)
    print(f"{sym} {tf}: trades={m['trades']} net={m['netPct']:.2f}% win={m['win']:.1f}% PF={m['pf']:.2f} DD={m['maxDD']:.2f}% ({time.time()-t0:.1f}s)")
    for k, v in sorted(m["by"].items()):
        print(f"   {k:10s} n={v[0]:4d} win={100*v[1]/max(v[0],1):5.1f}% PF={(v[2]/v[3]) if v[3] else float('inf'):.2f} net={v[2]-v[3]:.1f}")
