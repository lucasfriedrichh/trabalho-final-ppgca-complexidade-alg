# Problema do Caixeiro Viajante (TSP)

Comparação de três abordagens para encontrar um circuito que visita todas as cidades e volta à origem: **algoritmo genético**, **guloso de arestas** e **força bruta**. As instâncias vêm da base [Traveling Salesman Problem (TSPLIB) Dataset](https://www.kaggle.com/datasets/ziya07/traveling-salesman-problem-tsplib-dataset), do Kaggle. Em cada tamanho, as três abordagens resolvem **a mesma instância**.

## Base de dados

É usado o arquivo `tsp_dataset.csv`, com 2.783 instâncias euclidianas de **20 a 100 cidades** e coordenadas entre 0 e 100. De cada linha são lidos `instance_id`, `num_cities`, `city_coordinates` e `distance_matrix`. Antes do uso, a matriz é validada: precisa ser quadrada, simétrica, não negativa e ter diagonal zero.

As colunas `best_route` e `total_distance` **não são usadas**. `best_route` contém apenas rótulos (`Route_0` a `Route_4`), não uma rota. `total_distance` não corresponde a nenhuma rota reconstruível das cidades. Por isso, a base não traz um ótimo de referência. O outro arquivo do pacote, `tsp_instances_dataset.csv`, também não é usado, porque seus nomes não batem com os tamanhos (a linha `a280`, por exemplo, tem 54 cidades).

Na primeira execução, `util.ensure_dataset()` baixa a base (~90 MB compactada) para `data/tsp_dataset.csv`, pasta ignorada pelo git. Sem acesso à internet, baixe o arquivo manualmente pelo link acima e salve-o nesse caminho.

**Casos do benchmark.** Para cada tamanho de 20 a 100, de 10 em 10, é usada a instância de menor `instance_id`. Como a base começa em 20 cidades, os casos de **8, 9 e 10 cidades** são sub-instâncias com as primeiras cidades da instância de 20 (`#20`). Nelas a força bruta obtém o ótimo exato, que serve de referência para as outras abordagens.

## Instalação

É necessário Python 3.10 ou mais recente. Crie um ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Em Linux/macOS, ative com `source .venv/bin/activate`.

## Algoritmos

| Arquivo | Abordagem | Complexidade |
| :--- | :--- | :--- |
| [`brute_force.py`](brute_force.py) | Enumera todos os circuitos com a cidade 0 fixa, avaliando cada ciclo em um único sentido | `(n-1)!/2` rotas, O(n!) |
| [`greedy_tsp.py`](greedy_tsp.py) | Guloso de arestas: adiciona a menor aresta que não cria cidade de grau 3 nem ciclo prematuro (*union-find*) e, no fim, liga as duas pontas | O(n² log n) |
| [`genetic.py`](genetic.py) | População aleatória, seleção por torneio, elitismo, cruzamento OX (*order crossover*) e mutação por inversão de trecho | O(G · P · n) |

[`util.py`](util.py) reúne as funções compartilhadas: download e leitura da base, a classe `Instance` (com sub-instâncias via `prefix`), `route_cost`, `is_valid_route` e o cronômetro `timed`. Cada abordagem expõe uma função `solve_*`, que recebe a matriz de distâncias e devolve uma `Solution` (rota, distância e status).

Parâmetros padrão do genético: população 200, 1.500 gerações, cruzamento 0,9, mutação 0,6, torneio de 5 e elite de 4. A população inicial é **totalmente aleatória**, sem semente gulosa. Assim, a vantagem sobre o guloso vem da evolução, não de uma rota inicial pronta.

## Comparação

```powershell
python benchmark.py
```

O [`benchmark.py`](benchmark.py) chama `run_genetic`, `run_greedy` e `run_brute_force` para cada caso e confere se todas as rotas são válidas. Ele salva [o gráfico](docs/graphs/comparison.png), [a tabela](docs/tables/benchmark.md) e [os valores em CSV](docs/tables/results.csv), atualizando os arquivos ao fim de cada caso. A distância inclui o retorno à cidade inicial. A coluna `vs guloso` mostra a diferença percentual em relação ao guloso (valores negativos indicam rota menor). Com os tamanhos padrão, a execução leva cerca de **75 segundos**, quase todos gastos pelo genético.

**Força bruta.** A força bruta é executada **até 15 cidades**, com prazo de `600` s, ajustável com `--brute-timeout SEGUNDOS`. Com 8, 9 e 10 cidades ela termina em menos de 1 s, com status `ok`. **A partir de 16 cidades ela não é executada**: a linha recebe status `timeout`, sem distância nem tempo, porque `15!/2` já passa de 650 bilhões de rotas.

Para repetir ou variar a configuração:

```powershell
python benchmark.py --sizes 8 9 10 20 30 40 50 60 70 80 90 100 --generations 1500 --population 200 --seed 42
```

Tamanhos menores que 20 viram sub-instâncias da instância de 20 cidades; os demais precisam existir na base (qualquer valor de 20 a 100). Cada caso roda uma única vez, então a comparação não é uma estimativa estatística. As instâncias de tamanhos diferentes são independentes; por isso, compare as abordagens **dentro de cada tamanho**.

## GIFs

```powershell
python generate_gifs.py
```

Por padrão, são gerados GIFs para 10, 20, 50 e 100 cidades em [`docs/gifs`](docs/gifs/):

- **Guloso:** arestas adicionadas da menor para a maior.
- **Genético:** melhor rota e curva da melhor distância por geração.
- **Força bruta:** cada melhoria encontrada durante a enumeração. Só é gerado até 10 cidades.

Use `python generate_gifs.py --help` para escolher tamanhos ou ajustar a execução.

## Testes

```powershell
python -m unittest discover tests
```

Os testes verificam a leitura e a validação da base, com um CSV sintético. Também comparam a força bruta com um oráculo que avalia todas as permutações e conferem que o guloso acha o ótimo num polígono convexo. Para o genético, confirmam que os operadores preservam permutações e que a execução é determinística para uma mesma semente.
