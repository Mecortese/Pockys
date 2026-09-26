"""Descarga de datos históricos para el backtest.

- Cripto: velas de 5m de Binance Futuros USDT-M (data.binance.vision), archivos mensuales + diarios.
- Oro / Nasdaq: velas de 1m de Dukascopy (datafeed.dukascopy.com), remuestreadas a 5m.
Resultado: data/<SIMBOLO>_5m.csv con columnas time(ms UTC), open, high, low, close, volume.
"""
import io, lzma, struct, sys, time, zipfile, datetime as dt
import urllib.request
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0"}

def fetch(url, tries=8):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(min(2 ** k, 30))
        except Exception:
            time.sleep(min(2 ** k, 30))
    raise RuntimeError("no se pudo descargar " + url)

def binance(symbol, start, end, interval="5m"):
    frames = []
    base = "https://data.binance.vision/data/futures/um"
    m = dt.date(start.year, start.month, 1)
    while m <= end:
        tag = f"{m.year}-{m.month:02d}"
        raw = fetch(f"{base}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{tag}.zip")
        if raw is None:  # mes en curso: archivos diarios
            d = m
            while d.month == m.month and d <= end:
                r2 = fetch(f"{base}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{d.isoformat()}.zip")
                if r2:
                    frames.append(_bz(r2))
                d += dt.timedelta(days=1)
        else:
            frames.append(_bz(raw))
        print(symbol, tag, flush=True)
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    df = pd.concat(frames).drop_duplicates("time").sort_values("time")
    return df

def _bz(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    f = z.open(z.namelist()[0])
    df = pd.read_csv(f, header=None)
    if not str(df.iloc[0, 0]).isdigit():   # algunos archivos traen cabecera
        df = df.iloc[1:]
    df = df.iloc[:, :6].astype(float)
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    df["time"] = df["time"].astype("int64")
    return df

def dukascopy(inst, start, end, scale):
    rows = []
    d = start
    while d <= end:
        if d.weekday() != 5:  # sábado sin datos
            url = f"https://datafeed.dukascopy.com/datafeed/{inst}/{d.year}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
            raw = fetch(url)
            if raw:
                data = lzma.decompress(raw)
                t0 = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
                for i in range(0, len(data), 24):
                    s, o, c, l, h, v = struct.unpack(">iiiiif", data[i:i + 24])
                    rows.append((t0 + s * 1000, o / scale, h / scale, l / scale, c / scale, v))
            time.sleep(0.3)
        if d.day == 1:
            print(inst, d.isoformat(), flush=True)
        d += dt.timedelta(days=1)
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df = df[df.volume > 0]
    # remuestreo a 5m
    df.index = pd.to_datetime(df.time, unit="ms", utc=True)
    o = df.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    o["time"] = (o.index.view("int64") // 1_000_000).astype("int64")
    return o.reset_index(drop=True)[["time", "open", "high", "low", "close", "volume"]]

if __name__ == "__main__":
    start, end = dt.date(2025, 3, 1), dt.date(2026, 9, 25)
    which = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "1h":   # historia larga en 1h para validar en 1h/4h
        df = binance(which, dt.date(2020, 1, 1), end, "1h")
        df.to_csv(f"data/{which}_1h.csv", index=False)
        print("OK", which, len(df))
        sys.exit()
    if which in ("BTCUSDT", "ETHUSDT"):
        df = binance(which, start, end)
    elif which == "XAUUSD":
        df = dukascopy("XAUUSD", start, end, 1000)
    elif which == "NAS100":
        df = dukascopy("USATECHIDXUSD", start, end, 1000)
    df.to_csv(f"data/{which}_5m.csv", index=False)
    print("OK", which, len(df))
