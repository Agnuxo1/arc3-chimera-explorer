# Registro de experimentos — arc-agi-3
Métrica: scorecard oficial arc_agi 0.9.8 (escala 0-100, nivel = min(115,(humano/agente)^2*100), ponderado por índice), 25 juegos públicos offline.

| id | fecha UTC | hipótesis | config | semillas | métrica | niveles | decisión |
|---|---|---|---|---|---|---|---|
| L001 | 29-10 05:45 | control: explorador de grafo con detección de novedad | explorer, 5000 acc. | 0 (env seed 0) | 0,0013 | 4 | referencia |
| L002 | 29-10 05:50 | H1: CHIMERA (memoria holográfica + reglas AC, persistente) supera al control | chimera, 5000 acc. | 0 | 0,0486 | 10 | prometedor; confirmar con 3 semillas (E002) |
| L003 | 29-10 07:40 | control con 3 semillas (semilla = semilla del entorno) | explorer, 5000 | 0,1,2 | 0,0013 ± 0 | 4/sem | los juegos son deterministas: la semilla del entorno no cambia nada |
| L004 | 29-10 07:45 | H1 con 3 semillas | chimera v1 (hash de fase sin sal) | 0,1,2 | 0,0474 ± 0 | 9/sem | 36× control; varianza nula por determinismo |
| L005 | 29-10 07:50 | ablación: memoria reiniciada en cada nivel | chimera v1 persist=false | 0,1,2 | 0,0474 | 10/sem | la persistencia no aporta en 5000 acc. (pocos niveles superados) |
| L006 | 29-10 07:55 | ablación sin reglas AC (OJO: ya con hash de fase nuevo) | use_ca=false | 0,1,2 | 0,1634 | 8/sem | no comparable con L004: cambió la proyección aleatoria |
| L007 | 29-10 08:00 | ablación sin META/MUERTE (hash nuevo) | use_goal=use_dead=false | 0,1,2 | 0,1617 | 8/sem | idem; la proyección holográfica introduce varianza grande → repetir con semillas que cambien la proyección (L008-L012) |
| L008 | 29-10 08:30-09:00 | H1 con 5 semillas de proyección holográfica (salt_seed) | chimera {'salt_seed': True} 5000 acc. | 0-4 | 0.0758 ± 0.0697 | 48 (12,9,8,10,9) | ver resumen |
| L009 | 29-10 08:30-09:00 | ablación sin reglas AC | chimera {'salt_seed': True, 'use_ca': False} 5000 acc. | 0-4 | 0.0799 ± 0.0701 | 42 (8,9,7,10,8) | ver resumen |
| L010 | 29-10 08:30-09:00 | ablación sin trazas META/MUERTE | chimera {'salt_seed': True, 'use_goal': False, 'use_dead': False} 5000 acc. | 0-4 | 0.0757 ± 0.0695 | 41 (8,7,8,10,8) | ver resumen |
| L011 | 29-10 08:30-09:00 | ablación memoria reiniciada por nivel | chimera {'salt_seed': True, 'persist': False} 5000 acc. | 0-4 | 0.0757 ± 0.0696 | 47 (12,8,8,10,9) | ver resumen |
| L012 | 29-10 08:30-09:00 | v2: + reglas locales para teclado (kb-CA) | chimera {'salt_seed': True, 'use_kbca': True} 5000 acc. | 0-4 | 0.0897 ± 0.0585 | 52 (13,9,11,9,10) | ver resumen |

## Percepción v2 (commit b395118: enmascara líneas de borde volátiles; afecta igual a control y CHIMERA). 5 semillas, 5000 acc.

| id | hipótesis | config | media ± sd semillas | niveles por semilla | vs control | vs L018 |
|---|---|---|---|---|---|---|
| L016 | control | {} | 0.1465 ± 0.0000 | [14, 14, 14, 14, 14] | referencia | — |
| L017 | H1 CHIMERA | {'salt_seed': True} | 0.3078 ± 0.1461 | [19, 18, 18, 21, 20] | Δ=+0.1613, +15/-2 juegos, p=0.0008 | Δ=-0.0854, +6/-6 juegos, p=0.4697 |
| L018 | CHIMERA + kb-CA (candidato S02) | {'salt_seed': True, 'use_kbca': True} | 0.3932 ± 0.1742 | [22, 21, 18, 19, 18] | Δ=+0.2467, +14/-3 juegos, p=0.0046 | referencia |
| L019 | ablación AC de clic | {'salt_seed': True, 'use_kbca': True, 'use_ca': False} | 0.4039 ± 0.0925 | [20, 20, 18, 18, 18] | Δ=+0.2574, +13/-3 juegos, p=0.0076 | Δ=+0.0107, +7/-7 juegos, p=0.5016 |
| L020 | ablación META/MUERTE | {'salt_seed': True, 'use_kbca': True, 'use_goal': False, 'use_dead': False} | 0.3961 ± 0.2087 | [21, 18, 18, 20, 17] | Δ=+0.2496, +14/-3 juegos, p=0.0067 | Δ=+0.0029, +7/-8 juegos, p=0.8904 |
| L021 | ablación persistencia | {'salt_seed': True, 'use_kbca': True, 'persist': False} | 0.3236 ± 0.1798 | [22, 21, 18, 18, 19] | Δ=+0.1771, +14/-3 juegos, p=0.0046 | Δ=-0.0696, +1/-3 juegos, p=nan |
| L022 | dim 2048 | {'salt_seed': True, 'use_kbca': True, 'dim': 2048} | 0.2913 ± 0.0963 | [18, 18, 18, 16, 16] | Δ=+0.1448, +12/-4 juegos, p=0.0214 | Δ=-0.1019, +7/-10 juegos, p=0.6777 |
| L023 | alpha 4 | {'salt_seed': True, 'use_kbca': True, 'alpha': 4.0} | 0.4216 ± 0.1961 | [21, 19, 18, 19, 20] | Δ=+0.2751, +14/-2 juegos, p=0.0034 | Δ=+0.0284, +7/-4 juegos, p=0.4648 |
| L024 | alpha 1 | {'salt_seed': True, 'use_kbca': True, 'alpha': 1.0} | 0.2869 ± 0.1697 | [22, 20, 18, 18, 17] | Δ=+0.1404, +13/-4 juegos, p=0.0448 | Δ=-0.1063, +2/-8 juegos, p=0.0371 |

Decisión: H1 CONFIRMADA (media y niveles mayores que el control, mejora > 1 sd, Wilcoxon por juego p<0,05 en todas las variantes). Componentes: diferencias no significativas frente a L018 salvo alpha 1 (peor, p=0,037). server-ia reproduce v1 en Linux (E001=L003, E002=L004).
