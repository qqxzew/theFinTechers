### dev seeds, p_inst=30

| cell | method | stealth recall (hit/n) | recall | precision | honest raised mean/max | net-only errors | first flag day median [95 % CI] | never flagged | CZK before first flag median [CI] |
|---|---|---|---|---|---|---|---|---|---|
| shared_none | a | 0.00 (0/40) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 113652] |
| shared_none | b | 0.00 (0/40) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 5/10 | 46550 [39782, 92325] |
| shared_none | c | 1.00 (40/40) | 1.00 | 0.93 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4730 [0, 13888] |
| shared_none | e | 0.00 (0/40) | 0.77 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [12.0, 32.0] | 5/10 | 45833 [39782, 62856] |
| shared_medium | a | 0.00 (0/50) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 113556] |
| shared_medium | b | 0.00 (0/50) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 24.0 [14.0, 32.0] | 5/10 | 46621 [39716, 74550] |
| shared_medium | c | 1.00 (50/50) | 1.00 | 0.93 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4789 [0, 13903] |
| shared_medium | e | 0.00 (0/50) | 0.75 | 0.93 | 0.0 / 0 | 0.0 | 26.0 [14.0, 32.0] | 5/10 | 45834 [39716, 74116] |
| shared_high | a | 0.00 (0/59) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 113312] |
| shared_high | b | 0.00 (0/59) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 14.0 [14.0, 17.0] | 1/10 | 41915 [34548, 52716] |
| shared_high | c | 1.00 (59/59) | 1.00 | 0.93 | 0.6 / 1 | 0.6 | 6.0 [4.0, 8.0] | 0/10 | 4877 [0, 13927] |
| shared_high | e | 0.00 (0/59) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 9/10 | 73727 [41170, 113312] |
| rotating_none | a | 0.00 (0/40) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] |
| rotating_none | b | 0.00 (0/40) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] |
| rotating_none | c | 0.00 (0/40) | 0.85 | 0.92 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] |
| rotating_none | e | 0.00 (0/40) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73486 [41335, 117285] |
| rotating_medium | a | 0.00 (0/50) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 117388] |
| rotating_medium | b | 0.00 (0/50) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 117388] |
| rotating_medium | c | 0.00 (0/50) | 0.85 | 0.92 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 117388] |
| rotating_medium | e | 0.00 (0/50) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73582 [41269, 117388] |
| rotating_high | a | 0.00 (0/59) | 0.72 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 117341] |
| rotating_high | b | 0.00 (0/59) | 0.83 | 0.93 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 117341] |
| rotating_high | c | 0.00 (0/59) | 0.85 | 0.92 | 0.6 / 1 | 0.6 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 117341] |
| rotating_high | e | 0.00 (0/59) | 0.73 | 0.92 | 0.0 / 0 | 0.0 | 32.0 [32.0, 32.0] | 10/10 | 73727 [41170, 117341] |
| crimefree | a | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | b | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | c | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |
| crimefree | e | – (0/0) | – | 0.00 | 0.0 / 0 | 0.0 | – [–, –] | 0/0 | – [–, –] |

Collector buckets per world at month end (mean): crimefree: tested 71, flagged 0.0, institutional-suppressed 2.0; rotating_high: tested 80, flagged 11.0, institutional-suppressed 2.2; rotating_medium: tested 80, flagged 11.0, institutional-suppressed 2.2; rotating_none: tested 80, flagged 11.0, institutional-suppressed 2.2; shared_high: tested 82, flagged 13.0, institutional-suppressed 2.2; shared_medium: tested 82, flagged 13.0, institutional-suppressed 2.2; shared_none: tested 82, flagged 13.0, institutional-suppressed 2.2

| criterion | cell | value | result |
|---|---|---|---|
| S1 | crimefree/c | net-only errors 0.00 per seed | pass |
| S2 | shared_high | (c) 1.00 vs (b) 0.00, (a) 0.00, n=59 | pass |
| S2 | shared_medium | (c) 1.00 vs (b) 0.00, (a) 0.00, n=50 | pass |
| S2 | shared_none | (c) 1.00 vs (b) 0.00, (a) 0.00, n=40 | pass |
| S4 | rotating_high/c | honest raised mean 0.6, max 1 | pass |
| S4 | rotating_medium/c | honest raised mean 0.6, max 1 | pass |
| S4 | rotating_none/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_high/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_medium/c | honest raised mean 0.6, max 1 | pass |
| S4 | shared_none/c | honest raised mean 0.6, max 1 | pass |
| S5 | shared_high | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |
| S5 | shared_medium | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |
| S5 | shared_none | median first day (a) 32.0 vs (c) 6.0; never flagged (a) 10/10, (c) 0/10 | pass |