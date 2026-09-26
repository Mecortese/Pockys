# Resultados del backtest (réplica en Python del script)

Costos: comisión 0.04% por lado. Riesgo 0.5% del capital por operación, una posición a la vez, capital 10.000.
Ejecución estilo TradingView: señal al cierre, entrada a la apertura siguiente, stops/límites dentro de la vela.

## 1. Lógica original (CHOCH / Pullback BB / Rango) — sin ventaja

Año sep-2025 → sep-2026, valores por defecto:

| Activo | 5m | 15m | 1h | 4h |
|---|---|---|---|---|
| BTC | −30.7% (PF 0.74) | −5.6% (PF 0.66) | −0.9% (PF 0.87) | +3.9% (11 ops) |
| ETH | −38.1% (PF 0.73) | −3.5% (PF 0.81) | −2.7% (PF 0.53) | +2.0% (4 ops) |

Estudio de eventos sobre más de 21.000 CHOCH en 5m/15m: **sin comisión el resultado medio es ≈ 0R**
(−0.03R a +0.02R) en todos los contextos probados (tendencia 1h/4h, posición en la banda de 1h, recorrido
hasta la liquidez, barrido previo, ADX). Con comisión: −0.07R a −0.21R por operación.
Conclusión: el CHOCH del gráfico no predice la dirección; en 5m la comisión se lleva ~0.2R por operación.

## 2. Gatillos alternativos (1h de 2020 a 2026, BTC/ETH para elegir; SOL/oro/Nasdaq para validar)

R medio neto por operación con objetivo 2R, gráfico 4h:

| Gatillo | BTC+ETH | Validación (SOL, PAXG, XAUUSD, NAS100) |
|---|---|---|
| **Ruptura banda BB a favor de la tendencia** | **+0.22R** | **+0.30R** |
| Ruptura BB con filtro macro | +0.11R | +0.24R |
| Donchian 20 con filtro macro | +0.12R | +0.25R |
| CHOCH con tendencia | −0.04R | +0.21R |
| Rebote en la media BB | −0.14R | +0.13R |
| Rechazo de banda extrema | +0.09R | −0.04R |
| Reversión de rango | −0.04R | −0.34R |

En 1h ninguno supera ~+0.06R: la ventaja aparece en 4h.

## 3. Motor elegido: Ruptura BB con tendencia (gráfico 4h, confirmación D, macro W)

Salida: stop = extremo de 5 velas ± 0.5 ATR (mín. 1 ATR), objetivo 3R, breakeven en 1.5R,
cierre si hay CHOCH diario en contra.

| Activo | 2020 → 2026 | PF | DD máx. | Último año (sep-25 → sep-26) |
|---|---|---|---|---|
| ETH | +12.0% | 1.45 | 5.8% | −0.5% |
| SOL | +8.5% | 1.46 | 4.1% | −2.0% |
| Oro (PAXG) | +14.8% | 1.58 | 8.1% | +7.4% |
| Oro (XAUUSD, 2 años) | — | — | — | +3.9% |
| BTC | −3.8% | 0.87 | 10.6% | −4.5% |
| Nasdaq (2 años) | — | — | — | −1.6% |

Es una ventaja modesta de seguimiento de tendencia: gana cuando hay tendencia (oro 2025-26, cripto 2020-21 y
2023-24) y pierde poco en años laterales. Pocas operaciones: 6 a 17 por año y activo en 4h.

## Cómo reproducir

```
cd backtest
python3 download.py BTCUSDT 1h        # datos (Binance / Yahoo)
python3 study.py BTCUSDT,ETHUSDT 240 ruptura_3R
python3 events.py BTCUSDT 5           # estudio de eventos CHOCH
python3 alt.py 240 BTCUSDT,ETHUSDT    # gatillos alternativos
```
