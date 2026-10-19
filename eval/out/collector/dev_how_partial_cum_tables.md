### dev_how_partial seeds, p_inst=30

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag median [CI] |
|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/23) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 117285] |
| shared_none | b | 0.74 (17/23) | 0.95 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 32.0] | 2/6 | 44769 [37247, 110019] |
| shared_none | c | 1.00 (23/23) | 1.00 | 0.85 | 0.7 / 1 | 0.7 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] |
| shared_none | d | 1.00 (23/23) | 1.00 | 0.83 | 3.0 / 7 | 3.0 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] |
| shared_none | d2 | 1.00 (23/23) | 1.00 | 0.69 | 23.7 / 32 | 23.7 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] |
| shared_none | e | 0.13 (3/23) | 0.79 | 0.91 | 0.0 / 0 | 0.0 | 15.0 [8.0, 32.0] | 2/6 | 44769 [30441, 62856] |
| shared_medium | a | 0.00 (0/31) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 113652] |
| shared_medium | b | 0.55 (17/31) | 0.93 | 0.85 | 0.0 / 0 | 0.0 | 23.0 [14.0, 32.0] | 3/6 | 60727 [38163, 109724] |
| shared_medium | c | 1.00 (31/31) | 1.00 | 0.85 | 0.7 / 1 | 0.7 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] |
| shared_medium | d | 1.00 (31/31) | 1.00 | 0.84 | 2.7 / 7 | 2.7 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] |
| shared_medium | d2 | 1.00 (31/31) | 1.00 | 0.69 | 23.3 / 28 | 23.3 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] |
| shared_medium | e | 0.03 (1/31) | 0.76 | 0.91 | 0.0 / 0 | 0.0 | 24.0 [8.0, 32.0] | 3/6 | 46751 [36443, 95821] |
| shared_high | a | 0.00 (0/36) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 113517] |
| shared_high | b | 1.00 (36/36) | 1.00 | 0.86 | 0.0 / 0 | 0.0 | 14.0 [14.0, 18.0] | 0/6 | 39617 [31074, 52716] |
| shared_high | c | 1.00 (36/36) | 1.00 | 0.85 | 0.7 / 1 | 0.7 | 7.0 [4.0, 8.0] | 0/6 | 4877 [0, 30934] |
| shared_high | d | 1.00 (36/36) | 1.00 | 0.84 | 2.3 / 6 | 2.3 | 7.0 [4.0, 8.0] | 0/6 | 4877 [0, 30934] |
| shared_high | d2 | 1.00 (36/36) | 1.00 | 0.69 | 23.3 / 29 | 23.3 | 7.0 [4.0, 8.0] | 0/6 | 4877 [0, 30934] |
| shared_high | e | 0.00 (0/36) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 113517] |
| rotating_none | a | 0.00 (0/23) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] |
| rotating_none | b | 0.00 (0/23) | 0.85 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] |
| rotating_none | c | 0.00 (0/23) | 0.85 | 0.83 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] |
| rotating_none | d | 0.91 (21/23) | 0.98 | 0.83 | 3.0 / 7 | 3.0 | 7.0 [5.0, 10.0] | 0/6 | 16878 [4612, 31207] |
| rotating_none | d2 | 1.00 (23/23) | 1.00 | 0.69 | 23.7 / 32 | 23.7 | 7.0 [4.0, 8.0] | 0/6 | 4730 [0, 31207] |
| rotating_none | e | 0.00 (0/23) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73486 [38229, 113742] |
| rotating_medium | a | 0.00 (0/31) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 117388] |
| rotating_medium | b | 0.00 (0/31) | 0.85 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 117388] |
| rotating_medium | c | 0.00 (0/31) | 0.85 | 0.83 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 117388] |
| rotating_medium | d | 0.84 (26/31) | 0.97 | 0.83 | 2.7 / 7 | 2.7 | 8.0 [4.0, 14.1] | 0/6 | 16660 [0, 53094] |
| rotating_medium | d2 | 0.94 (29/31) | 0.99 | 0.69 | 23.3 / 28 | 23.3 | 7.0 [4.0, 8.0] | 0/6 | 4789 [0, 31098] |
| rotating_medium | e | 0.00 (0/31) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73582 [38163, 117388] |
| rotating_high | a | 0.00 (0/36) | 0.73 | 0.82 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 117544] |
| rotating_high | b | 0.00 (0/36) | 0.85 | 0.84 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 117544] |
| rotating_high | c | 0.00 (0/36) | 0.85 | 0.83 | 0.7 / 1 | 0.7 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 117544] |
| rotating_high | d | 0.25 (9/36) | 0.89 | 0.82 | 2.3 / 6 | 2.3 | 7.0 [4.0, 32.0] | 2/6 | 16883 [0, 56745] |
| rotating_high | d2 | 0.69 (25/36) | 0.95 | 0.68 | 23.3 / 29 | 23.3 | 7.0 [4.0, 10.0] | 0/6 | 11120 [0, 33857] |
| rotating_high | e | 0.00 (0/36) | 0.74 | 0.90 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 6/6 | 73727 [38064, 117544] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | d | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | d2 | – (0/0) | – | 0.00 | 13.0 / 32 | 13.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 72, flagged 0.0, institutional-suppressed 1.7; rotating_high: tested 84, flagged 11.0, institutional-suppressed 2.0; rotating_medium: tested 84, flagged 11.0, institutional-suppressed 2.0; rotating_none: tested 84, flagged 11.0, institutional-suppressed 2.0; shared_high: tested 86, flagged 13.0, institutional-suppressed 2.0; shared_medium: tested 86, flagged 13.0, institutional-suppressed 2.0; shared_none: tested 86, flagged 13.0, institutional-suppressed 2.0

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S1 | crimefree/d | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 1.00, (a) 0.00, n=36 | fail |
| S2 | shared_medium | (c) 1.00 vs (b) 0.55, (a) 0.00, n=31 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.74, (a) 0.00, n=23 | fail |
| S3 | rotating_medium | (d)-(c) = 0.84, n=31 | pass |
| S3 | rotating_none | (d)-(c) = 0.91, n=23 | pass |
| S4 | rotating_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_high/d | honest raised mean 2.3, max 6 | pass |
| S4 | rotating_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_medium/d | honest raised mean 2.7, max 7 | pass |
| S4 | rotating_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | rotating_none/d | honest raised mean 3.0, max 7 | pass |
| S4 | shared_high/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_high/d | honest raised mean 2.3, max 6 | pass |
| S4 | shared_medium/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_medium/d | honest raised mean 2.7, max 7 | pass |
| S4 | shared_none/c | honest raised mean 0.7, max 1 | pass |
| S4 | shared_none/d | honest raised mean 3.0, max 7 | pass |
| S5 | rotating_medium | median first day (a) 32.0 vs (d) 8.0; never flagged (a) 6/6, (d) 0/6 | pass |
| S5 | rotating_none | median first day (a) 32.0 vs (d) 7.0; never flagged (a) 6/6, (d) 0/6 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 7.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 7.0; never flagged (a) 6/6, (c) 0/6 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 7.0; never flagged (a) 6/6, (c) 0/6 | pass |