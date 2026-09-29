# Problema do Caixeiro Viajante (TSP)

Comparação de três abordagens para encontrar um circuito que visita todas as cidades e volta à origem: **algoritmo genético**, **guloso de arestas** e **força bruta**. As instâncias vêm da base [Traveling Salesman Problem (TSPLIB) Dataset](https://www.kaggle.com/datasets/ziya07/traveling-salesman-problem-tsplib-dataset), do Kaggle, e do [TSPLIB](https://github.com/mastqe/tsplib) clássico, que tem ótimos publicados.

## Estrutura

| Arquivo | Responsabilidade |
| :--- | :--- |
| [`benchmarks.py`](benchmarks.py) | Ponto de entrada: roda todas as abordagens e gera GIFs, tabelas e gráficos |
| [`docs.py`](docs.py) | Gera gráficos, GIFs, tabelas e o resumo, salvos na pasta `docs/` |
| [`genetic.py`](genetic.py) | Toda a lógica do algoritmo genético |
| [`bruteforce.py`](bruteforce.py) | Toda a lógica da força bruta |
| [`greedy.py`](greedy.py) | Toda a lógica do guloso |
| [`utils.py`](utils.py) | Funções compartilhadas: download das bases (Kaggle e TSPLIB), leitura e validação das instâncias, custo e validação de rotas, cronômetro |

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

Esse comando roda todas as abordagens em todas as etapas e gera GIFs, tabelas e gráficos em `docs/`. A execução completa leva cerca de 30 minutos. Para rodar só uma parte:

```powershell
python benchmarks.py --only benchmark gifs   # benchmark principal e GIFs (~2 min)
python benchmarks.py --only E1 E8            # experimentos específicos
python benchmarks.py --docs-only             # refaz tabelas e gráficos a partir dos CSVs salvos
python benchmarks.py --help                  # todas as opções
```

| Etapa | O que faz | Tempo aprox. |
| :--- | :--- | ---: |
| `benchmark` | AG, guloso e força bruta em 8, 9, 10 e 20, 30, …, 100 cidades (uma instância por tamanho) | 1,2 min |
| `gifs` | Animações de cada abordagem com 10, 20, 50 e 100 cidades | 0,8 min |
| `E1` | Crescimento da força bruta de 4 a 12 cidades e projeção de O(n!) | 1 min |
| `E2` | Distância até o ótimo exato em 20 instâncias de 10 cidades | 1,4 min |
| `E3` | Os 81 tamanhos da base (20 a 100 cidades) | 8 min |
| `E4` | Variação entre instâncias: 5 por tamanho (20, 30, …, 100) | 4 min |
| `E5` | Guloso nas 2.783 instâncias da base | 0,2 min |
| `E6` | AG com 10 sementes e curva de convergência (20, 50 e 100 cidades) | 3 min |
| `E7` | 44 instâncias de 101 a 149 cidades (segundo CSV do Kaggle) | 6 min |
| `E8` | 24 instâncias do TSPLIB (48 a 442 cidades) com ótimo publicado | 4 min |

Cada etapa grava seus dados brutos em `docs/data/<etapa>.csv`. Ao final, o `docs.py` gera a partir desses CSVs:

- `docs/tables/*.md`: tabelas;
- `docs/graphs/*.png`: gráficos (`comparison.png` e um por experimento);
- `docs/gifs/*.gif`: animações;
- [`docs/README.md`](docs/README.md): resumo com gráficos e números principais, pronto para a apresentação.

## Bases de dados

Os downloads são feitos pelo `utils.py` na primeira execução e ficam em `data/`, pasta ignorada pelo git.

**Kaggle, `tsp_dataset.csv`.** São 2.783 instâncias euclidianas de **20 a 100 cidades**, com coordenadas entre 0 e 100. São usados `instance_id`, `num_cities`, `city_coordinates` e `distance_matrix`. A matriz é validada antes do uso: precisa ser quadrada, simétrica, não negativa e ter diagonal zero. As colunas `best_route` (que só tem rótulos como `Route_0`) e `total_distance` (que não corresponde a nenhuma rota reconstruível) **não são usadas**, porque a base não traz um ótimo de referência.

**Kaggle, `tsp_instances_dataset.csv`.** São 113 instâncias de 20 a 149 cidades, das quais são usadas as 44 com mais de 100. Os nomes da coluna `TSP_Instance` não correspondem às instâncias reais do TSPLIB (`berlin52`, por exemplo, tem 140 cidades). Por isso cada instância é identificada pela linha do arquivo (`K2-<linha>`), e as distâncias euclidianas são calculadas a partir das coordenadas.

**TSPLIB.** São 24 instâncias clássicas com ótimo publicado, baixadas do espelho [mastqe/tsplib](https://github.com/mastqe/tsplib), porque o servidor original de Heidelberg não responde. As distâncias seguem a definição oficial (EUC_2D arredondada e ATT), a mesma dos ótimos publicados. Essa implementação foi conferida com os comprimentos de rota canônica da documentação do TSPLIB: `pcb442` = 221440 e `att532` = 309636.

**Sub-instâncias.** A base do Kaggle começa em 20 cidades, e a força bruta não termina nesse tamanho. Por isso os casos com menos de 20 cidades usam as primeiras cidades de uma instância (`#20 (primeiras 10)`, por exemplo). Nesses casos a força bruta dá o ótimo exato, que serve de referência para as outras abordagens.

Sem acesso à internet, baixe os arquivos manualmente e salve-os em `data/` (CSV do Kaggle) e em `data/tsplib/` (`<nome>.tsp`).

## Algoritmos

| Arquivo | Abordagem | Complexidade |
| :--- | :--- | :--- |
| `bruteforce.py` | Enumera todos os circuitos com a cidade 0 fixa, avaliando cada ciclo em um único sentido | `(n-1)!/2` rotas, O(n!) |
| `greedy.py` | Guloso de arestas: adiciona a menor aresta que não cria cidade de grau 3 nem ciclo prematuro (*union-find*) e, no fim, liga as duas pontas | O(n² log n) |
| `genetic.py` | População aleatória, seleção por torneio, elitismo, cruzamento OX (*order crossover*) e mutação por inversão de trecho | O(G · P · n) |

Cada abordagem expõe uma função `solve_*`, que recebe a matriz de distâncias e devolve uma `Solution` (rota, distância e status). O `benchmarks.py` confere se toda rota devolvida é válida.

**Genético.** Parâmetros padrão: população 200, 1.500 gerações, cruzamento 0,9, mutação 0,6, torneio de 5 e elite de 4. A população inicial é **totalmente aleatória**, sem semente gulosa. Assim, a vantagem sobre o guloso vem da evolução, não de uma rota inicial pronta.

**Força bruta.** É executada **até 15 cidades**, com prazo de `600` s, ajustável com `--brute-timeout`. **A partir de 16 cidades ela não é executada** e recebe status `timeout`, porque `15!/2` já passa de 650 bilhões de rotas. No E1, o prazo é de 1 hora, para medir o tempo exato de até 12 cidades.

## Observações para a análise

- Cada algoritmo roda uma vez por instância, exceto no E6, que usa 10 sementes. Os percentuais indicam tendência, não intervalos de confiança.
- As instâncias de tamanhos diferentes são independentes. Compare as abordagens **dentro de cada instância**.
- No TSPLIB (E8), o AG com 1.500 gerações fica de 1% a 14% acima do ótimo até 198 cidades, mas piora muito a partir de 200 (de 20% a 208%). O guloso fica estável, de 9% a 36% acima do ótimo.
- A linha "BHH" nos gráficos é o limite do ótimo quando n tende ao infinito. É uma referência de tendência, não o ótimo destas instâncias.
