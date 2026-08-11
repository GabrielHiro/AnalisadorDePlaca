.PHONY: help build build-fast build-win build-win-cross debug clean

PYTHON ?= python3
VENV ?= .venv
PYTHON_VENV := $(VENV)/bin/python
DOCKER ?= docker
PYINSTALLER_WIN_IMAGE ?= cdrx/pyinstaller-windows:python3

help:
	@echo "Comandos disponiveis:"
	@echo "  make build        - build completo com PyInstaller"
	@echo "  make build-fast   - instala deps e gera build rapido"
	@echo "  make build-win    - gera .exe valido (execute no Windows)"
	@echo "  make build-win-cross - cross-compile Linux->Windows com Docker/Wine"
	@echo "  make debug        - roda a aplicacao em modo debug"
	@echo "  make clean        - remove artefatos de build"

build:
	@echo "[build] Atualizando dependencias de build"
	$(PYTHON) -m pip install -r requirements-build.txt
	@echo "[build] Gerando aplicativo"
	$(PYTHON) -m PyInstaller --noconfirm --clean AnalisadorDePlacas.spec

build-fast:
	@echo "[build-fast] Instalando dependencias basicas"
	$(PYTHON) -m pip install -r requirements.txt -r requirements-build.txt
	@echo "[build-fast] Gerando build rapido"
	$(PYTHON) -m PyInstaller --noconfirm --clean --distpath dist --workpath build-temp AnalisadorDePlacas.spec

build-win:
	@if [ "$$OS" != "Windows_NT" ]; then \
		echo "[build-win] ERRO: este alvo precisa rodar em Windows para gerar .exe valido."; \
		echo "[build-win] No Linux, o PyInstaller gera binario ELF (incompativel com Windows)."; \
		echo "[build-win] Execute no Windows: build_exe.bat ou make build-win em shell Windows."; \
		exit 2; \
	fi
	@echo "[build-win] Instalando dependencias para Windows"
	$(PYTHON) -m pip install -r requirements.txt -r requirements-build.txt
	@echo "[build-win] Gerando executavel Windows (.exe)"
	$(PYTHON) -m PyInstaller --noconfirm --clean --distpath dist/windows --workpath build-temp/windows AnalisadorDePlacas.spec

build-win-cross:
	@if [ "$$OS" = "Windows_NT" ]; then \
		echo "[build-win-cross] Use make build-win no Windows nativo."; \
		exit 2; \
	fi
	@if ! command -v $(DOCKER) >/dev/null 2>&1; then \
		echo "[build-win-cross] ERRO: Docker nao encontrado."; \
		echo "[build-win-cross] Instale Docker e tente novamente."; \
		exit 2; \
	fi
	@echo "[build-win-cross] Gerando .exe de Windows a partir de Linux com $(PYINSTALLER_WIN_IMAGE)"
	$(DOCKER) run --rm \
		-v "$(PWD):/src" \
		-w /src \
		$(PYINSTALLER_WIN_IMAGE) \
		bash -lc "python -m pip install --upgrade pip && python -m pip install -r requirements.txt -r requirements-build.txt && python -m PyInstaller --noconfirm --clean --distpath dist/windows --workpath build-temp/windows --name AnalisadorDePlacas.exe main.py"

debug:
	@echo "[debug] Iniciando aplicacao em modo debug"
	$(PYTHON) -m pdb main.py

clean:
	@echo "[clean] Removendo artefatos de build"
	rm -rf build build-temp dist __pycache__ ui/__pycache__ parser/__pycache__ organizer/__pycache__ review/__pycache__ tests/__pycache__