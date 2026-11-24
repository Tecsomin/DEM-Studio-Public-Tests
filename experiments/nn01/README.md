# NN-01 — Optimizador neuronal del selector de broad-phase (experimental)

Copyright (c) 2026 Chile Ingenieria SPA. Todos los derechos reservados.

## Alcance real

Se implementó un MLP pequeño en Python estándar, reproducible por semilla, que **aconseja** seleccionar entre `grid`, `compact` y `verlet` para búsqueda de candidatos de contacto según características de escena. **No altera DEM, leyes físicas ni integrador**, ni se ejecuta aún dentro del solver C++.

Datos de entrada por escena (JSONL): `case_id`, `features`, `ms_per_step`, `provenance`. Cada escena requiere medir los **tres algoritmos** bajo mismo hardware, compilador, condiciones iniciales y número de pasos completos. Se usan seis características: partículas, densidad de llenado, fracción de contactos, RMS de velocidad, triángulos STL y fracción de superficies móviles. `provenance` debe ser `measured` o `synthetic`, nunca mezclar resultados sintéticos con afirmaciones reales.

## Ejecución

```bash
python -m unittest discover -s tests -p test_nn_broadphase_advisor.py -v
python experiments/nn01/nn_broadphase_advisor.py train --cases mis_mediciones.jsonl --out modelo.json
python experiments/nn01/nn_broadphase_advisor.py recommend --model modelo.json --features-json escena.json
```

Este prototipo entrena una red de seis entradas, diez unidades ocultas y tres salidas de rendimiento estimado (log ms/paso). Usa un holdout por `case_id` para evitar fuga entre algoritmos de una misma escena. Los resultados indican exactitud y ganancia de selección sobre las escenas del holdout; no son prueba causal ni generalizan sin diversidad de geometría/hardware. Datos fuera del dominio de entrenamiento fuerzan consejo `compact` con estado `out_of_distribution_fallback`. El artefacto siempre declara `production_approved=false` y `solver_changed=false`.

## Gates para integrarlo al motor en el futuro

1. Capturar >=30 escenas representativas y >=3 repeticiones ABBA por estrategia, con datos reales procedentes de un motor físico validado.
2. Conservar separación por escena, geometría y hardware entre entrenamiento y holdout; comparar contra `compact` fijo, heurística simple y oráculo que conoce el mejor tiempo.
3. Medir costo total de selección e inferencia en ms/paso, RAM, variabilidad, determinismo y falsos positivos; exigir mejora neta **>=5 %** sostenida para evaluar integración experimental.
4. Demostrar igualdad de inventario de contactos, estado final x/v/omega y balances de momento/energía dentro de tolerancias físicas antes de considerar un switch real.
5. Mantener flags OFF y retorno determinista al algoritmo base ante OOD, datos corruptos o inestabilidad. Sin aprobación industrial de NN por superar tests sintéticos.

Alternativa NN-02 (GNN de contacto/surrogates) se investigará por separado: mayor potencial científico, pero también riesgo de deriva física y generalización; **no bloquear TRL 6 del motor tradicional con su desarrollo**.
