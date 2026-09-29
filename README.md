# Problema do Caixeiro Viajante (TSP)

Comparação de três abordagens para encontrar um circuito que visita todas as cidades e volta à origem: **força bruta**, **algoritmo genético** e **guloso**. As instâncias vêm da base [Traveling Salesman Problem (TSPLIB) Dataset](https://www.kaggle.com/datasets/ziya07/traveling-salesman-problem-tsplib-dataset), do Kaggle.

São feitas **5 execuções**, cada uma com uma quantidade diferente de cidades. Nelas, as três abordagens resolvem a mesma instância e são comparados o **tempo de execução**, a **distância total** obtida e a **diferença** entre elas. A tabela de comparação fica em [`docs/README.md`](docs/README.md).

## Estrutura

| Arquivo | Responsabilidade |
| :--- | :--- |
| [`benchmarks.py`](benchmarks.py) | Ponto de entrada: roda as três abordagens nas 5 execuções e gera GIFs, tabelas e gráficos |
| [`docs.py`](docs.py) | Gera gráficos, GIFs e tabelas, salvos na pasta `docs/` |
| [`genetic.py`](genetic.py) | Toda a lógica do algoritmo genético |
| [`bruteforce.py`](bruteforce.py) | Toda a lógica da força bruta |
| [`greedy.py`](greedy.py) | Toda a lógica do guloso |
| [`utils.py`](utils.py) | Funções compartilhadas: download da base pela API do Kaggle, leitura e validação das instâncias, custo e validação de rotas, cronômetro |

## Instalação

É necessário Python 3.10 ou mais recente. Crie um ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Em Linux/macOS, ative com `source .venv/bin/activate`.

## Como executar

```powershell
python benchmarks.py
```

A execução leva cerca de 1 minuto e 20 segundos. Na primeira vez, a base do Kaggle (~90 MB compactada) é baixada para `data/tsp_dataset.csv`, pasta ignorada pelo git. Opções:

```powershell
python benchmarks.py --sizes 8 12 30 60 90   # outras quantidades de cidades
python benchmarks.py --seed 7                # outra semente para o genético
python benchmarks.py --help
```

| Execução | Cidades | Instância | Por quê |
| ---: | ---: | :--- | :--- |
| 1 | 8 | `#20 (primeiras 8)` | A força bruta termina: ótimo exato como referência |
| 2 | 12 | `#20 (primeiras 12)` | A força bruta ainda termina, mas já leva ~20 s |
| 3 | 20 | `#20` | Menor instância da base; força bruta inviável |
| 4 | 50 | `#132` | Tamanho intermediário |
| 5 | 100 | `#56` | Maior instância da base |

`#id` é o `instance_id` da base; para cada tamanho, é usada a instância de menor `instance_id`. Como a base começa em 20 cidades, as execuções 1 e 2 usam só as primeiras cidades da instância #20.

## Resultados gerados em `docs/`

- [`docs/README.md`](docs/README.md): **tabelas de comparação** (distância total e tempo de execução, com as diferenças entre as abordagens), gráfico e GIFs;
- `docs/graphs/comparison.png`: distância, tempo e diferença em relação ao guloso;
- `docs/gifs/`: animações de cada abordagem em cada execução (a da força bruta, só quando ela é executada);
- `docs/tables/results.md`: resultado de cada abordagem em cada execução;
- `docs/data/results.csv`: dados brutos.

## Algoritmos

| Arquivo | Abordagem | Complexidade |
| :--- | :--- | :--- |
| `bruteforce.py` | Enumera todos os circuitos com a cidade 0 fixa, avaliando cada ciclo em um único sentido | `(n-1)!/2` rotas, O(n!) |
| `greedy.py` | Guloso de arestas: adiciona a menor aresta que não cria cidade de grau 3 nem ciclo prematuro (*union-find*) e, no fim, liga as duas pontas | O(n² log n) |
| `genetic.py` | População aleatória, seleção por torneio, elitismo, cruzamento OX (*order crossover*) e mutação por inversão de trecho | O(G · P · n) |

Cada abordagem expõe uma função `solve_*`, que recebe a matriz de distâncias e devolve a rota, a distância e o status. O `benchmarks.py` confere se toda rota devolvida é válida.

**Genético.** Parâmetros: população 200, 1.500 gerações, cruzamento 0,9, mutação 0,6, torneio de 5 e elite de 4. A população inicial é totalmente aleatória, sem semente gulosa.

**Força bruta.** É executada até 15 cidades, com prazo de `600` s (`--brute-timeout`). **A partir de 16 cidades ela não é executada** e fica registrada como `timeout`, porque `15!/2` já passa de 650 bilhões de rotas.

## Base de dados

São usados `instance_id`, `num_cities`, `city_coordinates` e `distance_matrix` do arquivo `tsp_dataset.csv`: 2.783 instâncias euclidianas de 20 a 100 cidades, com coordenadas entre 0 e 100. A matriz é validada antes do uso: precisa ser quadrada, simétrica, não negativa e ter diagonal zero. As colunas `best_route` (que só tem rótulos como `Route_0`) e `total_distance` (que não corresponde a nenhuma rota reconstruível) não são usadas. Por isso, o ótimo de referência só existe quando a força bruta é executada.

Sem acesso à internet, baixe `tsp_dataset.csv` pela página do Kaggle e salve-o em `data/`.

## Observações

- Cada abordagem roda uma vez por execução, e os tempos dependem da máquina.
- Os GIFs são desenhados a partir da mesma execução medida, com base no histórico de cada abordagem.
- As instâncias de tamanhos diferentes são independentes. Compare as abordagens **dentro de cada execução**.
