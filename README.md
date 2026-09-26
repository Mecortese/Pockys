# Pockys

## SMC MTF Bollinger + CHOCH Scalping Strategy (Pine Script v5)

Archivo: [`SMC_MTF_Bollinger_Strategy.pine`](SMC_MTF_Bollinger_Strategy.pine)

### Motor recomendado (validado en backtest): Ruptura BB con tendencia
Usar en el gráfico de **4h** (confirmación Diario, macro Semanal, automático). Compra cuando el gráfico cierra por
encima de la banda BB superior con estructura alcista en D y W y el semanal sobre su media BB; venta espejo.
Stop en el extremo de 5 velas ± 0.5 ATR, objetivo 3R, breakeven en 1.5R, cierre si hay CHOCH diario en contra.
Resultados completos en [`backtest/RESULTADOS.md`](backtest/RESULTADOS.md).

### Motores de entrada (opcionales, sin ventaja en el backtest)
| Motor | Cuándo entra |
|---|---|
| **Pullback BB** | Tendencia 4h + 1h alineada, retroceso a la banda de Bollinger contraria del LTF, toma de liquidez (barrido / FVG / extremos BB 4h-1h) y patrón de giro. |
| **Scalp CHOCH** | El precio viene en contra, toma liquidez y hace un **CHOCH en el timeframe del gráfico** (15m / 5m / 1m). Entrada a mercado o con límite en el retesteo del nivel roto. |

### Clasificación de la entrada (igual en cualquier LTF)
| Tipo | Confluencia | Gestión por defecto |
|---|---|---|
| **SCALP** | Sólo el LTF | TP 1:1.5, cierre si hay CHOCH LTF en contra, reversa directa permitida |
| **INTRADÍA** | LTF + estructura 1h a favor (p. ej. CHOCH 5m + CHOCH 1h) | TP fijo 1:2, breakeven en 1.5R, cierre si CHOCH 1h en contra |
| **SWING** | LTF + 1h + 4h a favor | TP fijo 1:3, breakeven en 1.5R (opcional: parcial + runner con trailing) |

Si entras como SCALP y después la 1h (o 1h + 4h) confirma en tu dirección, la operación se **asciende**
automáticamente (etiqueta `⬆ INTRADÍA` / `⬆ SWING`): se amplía el TP, se activa breakeven/trailing y se deja correr.

### Ajustes orientativos para scalping agresivo
| LTF | Fractal estructura LTF | Ventana liquidez | Colchón SL | Riesgo máx. |
|---|---|---|---|---|
| 15m | 3 | 10 | 0.3 ATR | 3 ATR |
| 5m  | 2 | 15 | 0.3 ATR | 3 ATR |
| 1m  | 2 | 20 | 0.5 ATR | 4 ATR |

En 1m ajusta comisión y slippage en *Properties*: con muchas operaciones pesan mucho en el resultado.

### Cómo leer el gráfico
- **Etiqueta verde ▲ "COMPRA"** / **roja ▼ "VENTA"** = señal de entrada. El texto indica el tipo (SCALP / INTRADÍA / SWING) y el TP.
  El color indica la **dirección**; cuanto más opaca, más fuerte es la confluencia.
- **Línea roja / verde** = Stop Loss / Take Profit de la operación abierta.
- **Fondo verde / rojo** = 4h y 1h están de acuerdo (sesgo alcista / bajista).
- **Flechas de TradingView** (azul / rojo / violeta) = órdenes ya ejecutadas por el backtest, no son señales nuevas.
- El panel dice el **sesgo**, qué tipo sería una compra o una venta *en este momento* y cuál es el **próximo gatillo** a esperar.
- **Modo visual "Limpio"** (por defecto) oculta BB de 1h/4h, zonas de liquidez, FVG y barridos; "Completo" los muestra.
- Usar en el gráfico de **15m / 5m / 1m**. En 1h o 4h las bandas de 1h/4h dejan de tener sentido y las entradas se bloquean.

### Recorrido y salida por zonas de liquidez (por defecto)
- **Filtro de recorrido**: antes de entrar se mide la distancia hasta la primera zona de liquidez HTF en contra
  (banda BB opuesta de 1h/4h, swing high/low sin romper de 1h/4h). Si es menor que 2R, no se entra.
- **Salida**: se cierra un % en la primera zona de liquidez (≥ 1R asegurado, normalmente ≥ 2R), el stop pasa a
  breakeven y el resto corre hacia la siguiente zona con trailing ATR, o hasta un CHOCH de 1h en contra.

### Modo rango (lateral)
Cuando el ADX de 1h está bajo el mercado está en rango: se compra en el 25% inferior de la banda de 1h y se vende
en el 25% superior, tras toma de liquidez + CHOCH del gráfico. Salida completa y rápida en la media de la banda
de 1h (o en la banda opuesta). Etiqueta "RANGO (rápido)", fila propia en la tabla de estadísticas.

### Multi-activo
Todo se mide en ATR y porcentajes, así que sirve para BTC, otras criptos, oro o Nasdaq. Ajustá la comisión/spread
del activo en *Propiedades* y en el input "Comisión por lado".

### Afinar con datos
- **Tabla de estadísticas** (abajo a la izquierda): operaciones, % de acierto, PF y neto por tipo (SCALP / INTRADÍA / SWING × CHOCH / Pullback). Desactivá los tipos con PF < 1.
- **Filtros de calidad**: ADX de 1h (rango vs. tendencia), estructura LTF girada a favor para los Pullback, riesgo mínimo vs. comisión, pausa tras pérdida, horario.
- **Tamaño por riesgo**: cada operación arriesga un % fijo del capital (0.5% por defecto) con tope de apalancamiento.

### Timeframes automáticos (por defecto)
| Gráfico | Confirmación | Macro |
|---|---|---|
| 1m – 30m | 1h | 4h |
| 1h | 4h | Diario |
| 2h – 4h | Diario | Semanal |

Funciona en 5m, 15m, 1h y 4h sin tocar nada. En 1h/4h TradingView carga años de historia: ideal para validar el backtest.

### Uso
1. Pega el script en el Pine Editor de TradingView y pulsa *Add to chart*.
2. Pon el gráfico en el mismo timeframe que el input **LTF · Entrada** (por defecto 5m).
3. Elige el motor (Ambos / Sólo Pullback / Sólo Scalp) y ajusta los R:R de cada tipo.
4. Para alertas: *Crear alerta → "alert() function calls only"*.

Los datos de 4h/1h se leen sólo de velas cerradas (`expr[1]` + `lookahead_on`), por lo que la estrategia no repinta.
