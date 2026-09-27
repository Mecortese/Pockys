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

## 6. ⚠ INVÁLIDO (ver sección 9) — Entradas de 5m con respaldo D+4h+1h (objetivo del usuario: SL a la entrada y dejar correr) — `python3 be5.py BTCUSDT,ETHUSDT`

Stop = extremo de 10 velas ± 0.3 ATR (mín. por comisión). Gestión: SL a la entrada al llegar a +1R, objetivo 3R.
El precio llega a +1R antes del stop ~50% de las veces en cualquier contexto; lo que cambia con el respaldo es
cuánto corre después.

| Gatillo 5m | Con D+4h+1h a favor | Sin respaldo | 1ª mitad / 2ª mitad (con respaldo) |
|---|---|---|---|
| Ruptura banda BB | **+0.15R** | −0.08R | +0.23R / +0.08R |
| CHOCH | **+0.13R** | −0.02R | +0.16R / +0.09R |
| Rebote media BB | +0.15R | −0.04R | +0.32R / −0.02R (descartado) |

Costo de comisión incluido (~0.18R por operación).

## 7. ⚠ INVÁLIDO (ver sección 9) — Motor "Respaldo" en 5m / 15m / 1h / 4h (BTC + ETH) — `python3 be_tf.py`

Gestión: SL a la entrada en +1R, objetivo 3R. R neto de comisión por señal (las señales pueden superponerse).

| Gráfico | Período | Con respaldo | Sin respaldo | Señales/mes por activo (con respaldo) |
|---|---|---|---|---|
| 5m | último año | **+0.14R** | −0.06R | ~120 |
| 15m | último año | **+0.29R** | +0.05R | ~39 |
| 1h | último año | **+0.24R** | +0.22R | ~15 |
| 1h | 2020-2025 | **+0.25R** | +0.11R | ~15 |
| 4h | último año | −0.14R (92 señales) | +0.34R | ~4 |
| 4h | 2020-2025 | **+0.56R** | +0.13R | ~4 |

## 8. ⚠ INVÁLIDO (ver sección 9) — 5m: entradas anticipadas (15m todavía en retroceso)

5m con respaldo D+4h+1h, último año, BTC + ETH, SL a la entrada en +1R, objetivo 3R:

| Estructura 15m al momento de la señal | Señales | R medio | 1ª mitad / 2ª mitad |
|---|---|---|---|
| **En contra (retroceso)** | 1.301 | **+0.26R** | CHOCH +0.27 / +0.10 · Ruptura +0.44 / +0.25 |
| Ya a favor | 1.601 | +0.05R | CHOCH −0.01 / −0.07 · Ruptura +0.13 / +0.02 |

BTC: +0.17R vs +0.02R · ETH: +0.35R vs +0.08R. Activado por defecto en gráficos menores a 15m.

## 9. Corrección: réplica exacta del Probador (una operación a la vez) — `study.py ... rs_*`

Las secciones 6-8 tenían un error: al llegar a +1R no se aplicaba el SL movido a la entrada, así que operaciones
que volvían a la entrada se contaban igual como +3R. La réplica exacta coincide con TradingView
(BTC 5m, 6-26 sep 2026: réplica −4.6%, Probador −3.0%).

Último año, riesgo 0.5% por operación, comisión 0.04%:

| Gestión | BTC 5m | BTC 15m | ETH 5m | ETH 15m |
|---|---|---|---|---|
| SL a la entrada en +1R, TP 3R | −20.8% (PF 0.73) | +7.3% (1.18) | −4.0% (0.94) | +1.6% (1.04) |
| SL a la entrada en +2R, TP 3R | +5.3% (1.06) | +7.4% (1.17) | −9.1% (0.89) | +1.5% (1.04) |
| **Stop fijo, TP 3R** | **+9.7% (1.10)** | **+11.5% (1.28)** | +0.2% (1.00) | **+8.2% (1.20)** |
| Stop fijo, TP 2R | −6.3% (0.93) | +2.3% (1.04) | −8.7% (0.90) | +6.3% (1.13) |

Stop fijo + 3R: BTC 5m positivo en ambas mitades (+3.0% / +6.7%), BTC 15m (+5.7% / +5.8%),
ETH 15m (+8.4% / −0.2%). Mover el SL a la entrada temprano corta las operaciones que después llegan a 3R.

## 10. Explosión tras compresión (squeeze) — réplica exacta, último año

Entrada en la primera vela que cierra fuera de la banda tras una compresión (ancho de banda en el 20% más bajo),
stop del otro lado de la compresión, sin filtro de tendencia (o con filtro macro):

| | 5m | 15m |
|---|---|---|
| BTC 3R | −71.5% (PF 0.66) | −25.0% (PF 0.77) |
| ETH 3R | −48.5% (PF 0.81) | −12.7% (PF 0.88) |
| BTC 3R + filtro macro | −58.5% | −16.5% |

Las rupturas desde compresión en 5m/15m son mayormente falsas: no sirven como entrada mecánica.

## 11. Comprar la liquidez del 4h con el diario a favor, y scalping con salida rápida — réplica exacta, último año

Respaldo "liq4h": diario alcista + precio tocó el 25% inferior de la banda de 4h en las últimas 8 h, gatillo liquidez + CHOCH.
Respaldo "trend": diario + 4h + 1h a favor (motor por defecto). Stop fijo en todos.

| Variante | BTC 5m | BTC 15m | ETH 5m | ETH 15m |
|---|---|---|---|---|
| trend, TP 3R (por defecto) | **+9.7%** | **+11.5%** | +0.2% | **+8.2%** |
| liq4h, TP 3R | −26.6% | −13.1% | −10.3% | +7.8% |
| trend, scalp TP 1R | −19.3% | +0.2% | −10.6% | +0.3% |
| trend, scalp TP 1.5R | −13.1% | −2.8% | −7.1% | +3.5% |
| liq4h, scalp TP 1R | −35.7% | −6.9% | −19.0% | −8.6% |
| liq4h, scalp TP 1.5R | −29.6% | −5.9% | −13.0% | +0.1% |

Scalping (salida en 1-1.5R) con comisión taker 0.04% no tiene ventaja: acierta ~50% y la comisión (~0.2R en 5m) lo vuelve negativo.
