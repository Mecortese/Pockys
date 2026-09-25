# Pockys

## SMC MTF Bollinger Pullback Strategy (Pine Script v5)

Archivo: [`SMC_MTF_Bollinger_Strategy.pine`](SMC_MTF_Bollinger_Strategy.pine)

Estrategia para TradingView que combina:

- **Filtro de tendencia multi-temporal**: estructura de mercado (BOS/CHOCH por fractales) en 4h y 1h, más precio 4h vs. media central de Bollinger 4h.
- **Entrada en retroceso** en el LTF (1h / 15m / 5m / 1m) sobre la banda de Bollinger contraria.
- **Confirmación SMC**: barrido de swings previos, toque de FVG (LTF y 1h) o de los extremos de BB 4h/1h (proxies de liquidez).
- **Confirmación de giro**: pin bar, envolvente o cruce de vuelta de la banda.
- **Riesgo**: SL bajo/sobre la vela o la zona de liquidez + colchón ATR, TP por R:R fijo, TP parcial opcional en la banda opuesta y cierre ante CHOCH de 1h en contra.

### Uso
1. Abre el Pine Editor en TradingView, pega el contenido del archivo y pulsa *Add to chart*.
2. Pon el gráfico en el mismo timeframe que el input **LTF · Entrada** (por defecto 15m).
3. Ajusta los parámetros en *Settings → Inputs* y revisa los resultados en el *Strategy Tester*.

Los datos de 4h/1h se leen sólo de velas cerradas (`expr[1]` + `lookahead_on`), por lo que la estrategia no repinta.
