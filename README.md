# Pockys

## SMC MTF Bollinger + CHOCH Scalping Strategy (Pine Script v5)

Archivo: [`SMC_MTF_Bollinger_Strategy.pine`](SMC_MTF_Bollinger_Strategy.pine)

### Motores de entrada
| Motor | Cuándo entra |
|---|---|
| **Pullback BB** | Tendencia 4h + 1h alineada, retroceso a la banda de Bollinger contraria del LTF, toma de liquidez (barrido / FVG / extremos BB 4h-1h) y patrón de giro. |
| **Scalp CHOCH** | El precio viene en contra, toma liquidez y hace un **CHOCH en el timeframe del gráfico** (15m / 5m / 1m). Entrada a mercado o con límite en el retesteo del nivel roto. |

### Clasificación de la entrada (igual en cualquier LTF)
| Tipo | Confluencia | Gestión por defecto |
|---|---|---|
| **SCALP** | Sólo el LTF | TP 1:1.5, cierre si hay CHOCH LTF en contra, reversa directa permitida |
| **INTRADÍA** | LTF + estructura 1h a favor (p. ej. CHOCH 5m + CHOCH 1h) | TP 1:3, parcial y breakeven en 1R, cierre si CHOCH 1h en contra |
| **SWING** | LTF + 1h + 4h a favor | TP 1:5 (u opcional sin TP), parcial, breakeven y trailing ATR |

Si entras como SCALP y después la 1h (o 1h + 4h) confirma en tu dirección, la operación se **asciende**
automáticamente (etiqueta `⬆ INTRADÍA` / `⬆ SWING`): se amplía el TP, se activa breakeven/trailing y se deja correr.

### Ajustes orientativos para scalping agresivo
| LTF | Fractal estructura LTF | Ventana liquidez | Colchón SL | Riesgo máx. |
|---|---|---|---|---|
| 15m | 3 | 10 | 0.3 ATR | 3 ATR |
| 5m  | 2 | 15 | 0.3 ATR | 3 ATR |
| 1m  | 2 | 20 | 0.5 ATR | 4 ATR |

En 1m ajusta comisión y slippage en *Properties*: con muchas operaciones pesan mucho en el resultado.

### Uso
1. Pega el script en el Pine Editor de TradingView y pulsa *Add to chart*.
2. Pon el gráfico en el mismo timeframe que el input **LTF · Entrada** (por defecto 5m).
3. Elige el motor (Ambos / Sólo Pullback / Sólo Scalp) y ajusta los R:R de cada tipo.
4. Para alertas: *Crear alerta → "alert() function calls only"*.

Los datos de 4h/1h se leen sólo de velas cerradas (`expr[1]` + `lookahead_on`), por lo que la estrategia no repinta.
