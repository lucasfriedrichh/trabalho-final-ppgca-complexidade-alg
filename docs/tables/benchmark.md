# Resultados do benchmark

Instância `#id` é o `instance_id` da base do Kaggle; `(primeiras k)` indica a sub-instância com as k primeiras cidades. `vs guloso`: diferença de distância em relação ao guloso (negativo = rota menor). `ok`: execução concluída (na força bruta, ótimo exato). `timeout`: a partir de 16 cidades a força bruta não é executada, pois as `(n-1)!/2` rotas não terminariam no prazo; entre 11 e 15 cidades, é a melhor rota encontrada em até 600 s.

| Cidades | Instância | Algoritmo | Distância percorrida | Tempo (s) | Status | vs guloso (%) |
| ---: | :--- | :--- | ---: | ---: | :--- | ---: |
| 8 | #20 (primeiras 8) | Genetic | 328,28 | 4,0425 | ok | +0,0 |
| 8 | #20 (primeiras 8) | Greedy | 328,28 | 0,0000 | ok | +0,0 |
| 8 | #20 (primeiras 8) | Brute force | 328,28 | 0,0021 | ok | +0,0 |
| 9 | #20 (primeiras 9) | Genetic | 328,77 | 3,6189 | ok | +0,0 |
| 9 | #20 (primeiras 9) | Greedy | 328,77 | 0,0000 | ok | +0,0 |
| 9 | #20 (primeiras 9) | Brute force | 328,77 | 0,0174 | ok | +0,0 |
| 10 | #20 (primeiras 10) | Genetic | 333,85 | 3,7836 | ok | +0,0 |
| 10 | #20 (primeiras 10) | Greedy | 333,85 | 0,0000 | ok | +0,0 |
| 10 | #20 (primeiras 10) | Brute force | 333,85 | 0,1791 | ok | +0,0 |
| 20 | #20 | Genetic | 465,69 | 4,0330 | ok | -19,5 |
| 20 | #20 | Greedy | 578,31 | 0,0001 | ok | +0,0 |
| 20 | #20 | Brute force | — | — | timeout | — |
| 30 | #69 | Genetic | 455,59 | 4,4072 | ok | -19,7 |
| 30 | #69 | Greedy | 567,49 | 0,0002 | ok | +0,0 |
| 30 | #69 | Brute force | — | — | timeout | — |
| 40 | #136 | Genetic | 546,34 | 4,9392 | ok | -12,3 |
| 40 | #136 | Greedy | 622,98 | 0,0002 | ok | +0,0 |
| 40 | #136 | Brute force | — | — | timeout | — |
| 50 | #132 | Genetic | 577,79 | 5,2648 | ok | -12,2 |
| 50 | #132 | Greedy | 658,27 | 0,0004 | ok | +0,0 |
| 50 | #132 | Brute force | — | — | timeout | — |
| 60 | #207 | Genetic | 617,82 | 5,7947 | ok | -13,6 |
| 60 | #207 | Greedy | 714,87 | 0,0006 | ok | +0,0 |
| 60 | #207 | Brute force | — | — | timeout | — |
| 70 | #65 | Genetic | 723,64 | 6,0297 | ok | -10,8 |
| 70 | #65 | Greedy | 811,70 | 0,0008 | ok | +0,0 |
| 70 | #65 | Brute force | — | — | timeout | — |
| 80 | #67 | Genetic | 747,95 | 6,2861 | ok | -10,1 |
| 80 | #67 | Greedy | 831,69 | 0,0011 | ok | +0,0 |
| 80 | #67 | Brute force | — | — | timeout | — |
| 90 | #88 | Genetic | 785,02 | 6,6527 | ok | -12,7 |
| 90 | #88 | Greedy | 899,47 | 0,0015 | ok | +0,0 |
| 90 | #88 | Brute force | — | — | timeout | — |
| 100 | #56 | Genetic | 877,25 | 6,9761 | ok | -12,3 |
| 100 | #56 | Greedy | 1000,77 | 0,0019 | ok | +0,0 |
| 100 | #56 | Brute force | — | — | timeout | — |
