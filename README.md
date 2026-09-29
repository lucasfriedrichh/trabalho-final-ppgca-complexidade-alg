# Problema do Caixeiro Viajante (TSP)

Comparação de três abordagens para encontrar um circuito que visita todas as cidades e volta à origem: algoritmo genético, força bruta e vizinho mais próximo (greedy). Os arquivos em `test_data/` fornecem as **mesmas cidades** para cada algoritmo, com 8, 16, 32 e 64 pontos.

## Instalação

É necessário Python 3.10 ou mais recente. Crie um ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Em Linux/macOS, ative com `source .venv/bin/activate`.

## Comparação

```powershell
python benchmark.py
```

O script executa cada abordagem sem animações durante a medição e salva `docs/comparison.png` (distância e tempo) e `docs/results.csv` (valores completos). A distância inclui o retorno à cidade inicial. O tempo mede apenas a busca da solução, sem geração do gráfico ou leitura dos arquivos. Para repetir uma configuração específica:

```powershell
python benchmark.py --generations 120 --population 50 --seed 42
```

A força bruta é **exata**, mas limitada a **8 cidades**. Ao fixar a cidade inicial, ela examina `(n-1)!` rotas; para 8 cidades são 5.040, enquanto para 16 seriam mais de 1,3 trilhão. Nas linhas de 16, 32 e 64 cidades, o CSV registra `skipped` e o gráfico omite o ponto da força bruta. A classe `BruteForce` também recusa entradas maiores que 8 cidades.

O greedy escolhe sempre a cidade não visitada mais próxima, com tempo quadrático em relação ao número de cidades. O genético usa uma população e um número fixo de gerações; sua qualidade pode variar com a semente. O gráfico compara qualidade e tempo, mas uma única execução por tamanho não constitui uma estimativa estatística de desempenho.

## GIFs

```powershell
python generate_gifs.py
```

Os GIFs das rotas e do progresso são gravados em `docs/`. Use `python generate_gifs.py --help` para selecionar tamanhos ou ajustar a execução.

## Testes

```powershell
python -m unittest discover -s tests
```

O `.gitignore` cobre ambientes virtuais, caches e arquivos gerados pelo Python. Os resultados em `docs/` podem ser versionados para acompanhar o trabalho.
"# trabalho-final-ppgca-complexidade-alg" 
