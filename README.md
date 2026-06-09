# Analisador de Placas

Aplicativo desktop para revisar imagens de placas descriptografadas, classificar cada captura e organizar os arquivos renomeados em pastas por equipamento, periodo e tipo de falha.

## Requisitos

- Python 3.10 ou superior
- Tkinter (incluso na instalacao padrao do Python no Windows)

## Instalacao

```bash
cd AnalisadorDePlaca
pip install -r requirements.txt
```

## Uso

1. Execute o aplicativo:

```bash
python main.py
```

2. Na secao **Configuracao inicial**, escolha:
   - **Pasta de origem** (busca imagens em subpastas)
   - **Pasta de saida** (onde as copias renomeadas serao salvas)

3. Clique em **Iniciar analise** para comecar a revisar.

4. Para cada imagem, escolha uma acao:
   - **Certo**: placa ja correta ou corrigida manualmente. Se o campo opcional estiver preenchido, usa essa placa no nome; se vazio, usa a placa detectada
   - **Falha tecnica**: imagem com falha de leitura; copia para a pasta `falha_tecnica`
   - **Obstrucao**: falha nao tecnica; placa `000000` na pasta `obstruida`

5. A cada confirmacao, a imagem e **copiada** (originais permanecem intactos) para a estrutura de pastas de saida.

6. Clique em **Gerar relatorio** a qualquer momento para salvar o CSV com o resumo do que ja foi classificado (nao e necessario terminar o lote).

## Formato do nome de entrada

Exemplo:

```text
00016052000SP05163400Leste114052026121553040040051014406FNH276800000000.JPG
```

Campos extraidos por posicao fixa (sem extensao, minimo 64 caracteres):

| Campo | Posicao | Exemplo |
|-------|---------|---------|
| Equipamento (`nSerie`) | 0-7 | `0001605` |
| Faixa | 7-8 (1 digito apos o serie) | `2` |
| Sentido | regex | `Leste` |
| Horario | 6 digitos apos sentido + 9 chars | `121553` |
| Placa | 6-7 chars imediatamente antes de 6+ zeros de padding | `FNH2768`, `FDS2S00` |

## Formato do nome de saida

```text
{nSerie}_{faixa}_SENTIDO_{periodo}_{horario}_{placa}.jpg
```

Exemplo:

```text
0001605_2_SENTIDO_D_121553_FNH2768.jpg
```

- **Periodo**: `D` (diurno, 06:00-17:59) ou `N` (noturno)
- **Obstrucao**: placa `000000`

## Estrutura de pastas gerada

```text
{pasta_saida}/{equipamento}/
  diurno/
    certo/
    falha_tecnica/
    obstruida/
  noturno/
    certo/
    falha_tecnica/
    obstruida/
```

- **Certo**: placa correta ou corrigida manualmente
- **Falha tecnica**: imagens com falha de leitura
- **Obstruida**: placas obstruidas (`000000`)

Um arquivo `relatorio.csv` e gerado na pasta de saida com o resumo numerico:

| Indicador | Descricao |
|-----------|-----------|
| Quantidade analisada | Total ja classificado (corretas + falhas), sem contar pendentes ou pulados |
| Placas corretas | Imagens marcadas como certo |
| Falhas tecnicas | Imagens marcadas como falha tecnica |
| Falhas por obstrucao | Imagens marcadas como obstrucao |

## Gerar executavel (.exe)

Requisito: Python 3.10+ instalado apenas para **compilar** (quem for usar o `.exe` nao precisa de Python).

### Opcao 1 — Script automatico

Na pasta do projeto, no **Prompt de Comando (cmd)**:

```bat
build_exe.bat
```

### Opcao 2 — Makefile

```bat
make build
```

Se `python` funcionar no seu terminal:

```bat
cd AnalisadorDePlaca
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean AnalisadorDePlacas.spec
```

**Importante:** use `python -m PyInstaller` (nao apenas `pyinstaller` ou `py`).

### Resultado

```text
dist\AnalisadorDePlacas.exe
```

Copie o `.exe` para onde quiser e execute com duplo clique. Na primeira abertura o Windows pode pedir confirmacao (SmartScreen).

A pasta `build/` e temporaria; pode apagar apos gerar o `.exe`.
