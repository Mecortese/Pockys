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

## 4. Estrategias clásicas publicadas (velas diarias, sin optimizar)

Datos: BTC 2014-2026, oro 2000-2026, Nasdaq 100 1985-2026 (Yahoo). Señal al cierre, ejecución a la apertura siguiente,
costos incluidos. `python3 classic.py`

| Estrategia | BTC anual / caída máx. | Oro | Nasdaq |
|---|---|---|---|
| Comprar y mantener | 63% / −83% | 11.3% / −45% | 13.7% / −83% |
| Momentum 12 meses (solo compra) | **67.8% / −71%** | 7.7% / −43% | 12.5% / −48% |
| Cruce medias 50/200 | 56.9% / −69% | 8.1% / −37% | **12.9% / −42%** |
| Sobre media 200 (Faber) | 60.8% / −70% | 8.0% / −38% | 11.6% / −54% |
| Turtle 55/20 compra y venta | 33.9% / −67% | −2.4% / −69% | 1.1% / −72% |
| Connors RSI2 | 10.0% / −35% | 0.9% / −17% | 3.7% / −38% |

En activos con tendencia alcista de largo plazo, los filtros de tendencia rinden parecido a comprar y mantener
pero cortan mucho las caídas. Vender en corto empeora los resultados en los tres.

## 5. Cartera BTC + Oro + Nasdaq con filtro de tendencia (2015-2026) — `python3 portfolio.py`

| Cartera | Anual | Caída máx. | Sharpe | Peor año |
|---|---|---|---|---|
| Comprar y mantener, 1/3 cada uno | 30.1% | −39.0% | 1.22 | −30.3% |
| Momentum 12m, 1/3 cada uno | 29.9% | −28.1% | 1.38 | −17.6% |
| **Momentum 12m, paridad de riesgo** | **16.4%** | **−10.6%** | **1.44** | **−2.9%** |
| Media 200, paridad de riesgo | 14.8% | −18.9% | 1.35 | −0.8% |

Implementado en `Cartera_Tendencia_BTC_Oro_Nasdaq.pine` (tablero + estrategia sobre el gráfico diario).

## 6. Entradas de 5m con respaldo D+4h+1h (objetivo del usuario: SL a la entrada y dejar correr) — `python3 be5.py BTCUSDT,ETHUSDT`

Stop = extremo de 10 velas ± 0.3 ATR (mín. por comisión). Gestión: SL a la entrada al llegar a +1R, objetivo 3R.
El precio llega a +1R antes del stop ~50% de las veces en cualquier contexto; lo que cambia con el respaldo es
cuánto corre después.

| Gatillo 5m | Con D+4h+1h a favor | Sin respaldo | 1ª mitad / 2ª mitad (con respaldo) |
|---|---|---|---|
| Ruptura banda BB | **+0.15R** | −0.08R | +0.23R / +0.08R |
| CHOCH | **+0.13R** | −0.02R | +0.16R / +0.09R |
| Rebote media BB | +0.15R | −0.04R | +0.32R / −0.02R (descartado) |

Costo de comisión incluido (~0.18R por operación).
