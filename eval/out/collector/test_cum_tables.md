### test seeds, p_inst=30

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag median [CI] |
|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/21) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] |
| shared_none | b | 0.00 (0/21) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 130407] |
| shared_none | c | 1.00 (21/21) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9350] |
| shared_none | e | 0.05 (1/21) | 0.81 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 3/6 | 42610 [35580, 63846] |
| shared_medium | a | 0.00 (0/31) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] |
| shared_medium | b | 0.29 (9/31) | 0.90 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [14.0, 32.0] | 4/6 | 38233 [30082, 130456] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9291] |
| shared_medium | e | 0.13 (4/31) | 0.78 | 0.92 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 3/6 | 42535 [35557, 63774] |
| shared_high | a | 0.00 (0/36) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] |
| shared_high | b | 0.67 (24/36) | 0.95 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 38165 [31887, 63666] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.85 | 1.7 / 4 | 1.7 | 8.0 [8.0, 8.0] | 0/6 | 0 [0, 9204] |
| shared_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] |
| rotating_none | a | 0.00 (0/21) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] |
| rotating_none | b | 0.00 (0/21) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] |
| rotating_none | c | 0.00 (0/21) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] |
| rotating_none | e | 0.00 (0/21) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67426 [35580, 119825] |
| rotating_medium | a | 0.00 (0/31) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] |
| rotating_medium | b | 0.00 (0/31) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] |
| rotating_medium | c | 0.00 (0/31) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] |
| rotating_medium | e | 0.00 (0/31) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67332 [35557, 130456] |
| rotating_high | a | 0.00 (0/36) | 0.75 | 0.83 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] |
| rotating_high | b | 0.00 (0/36) | 0.86 | 0.85 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] |
| rotating_high | c | 0.00 (0/36) | 0.86 | 0.84 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] |
| rotating_high | e | 0.00 (0/36) | 0.75 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 67192 [35523, 130529] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 79, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 79, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 81, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 81, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.67, (a) 0.00, n=36 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.29, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=21 | pass |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_high/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_medium/c | honest raised mean 1.7, max 4 | pass |
| S4 | shared_none/c | honest raised mean 1.7, max 4 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 8.0; never flagged (a) 6/6, (c) 0/6 | pass |