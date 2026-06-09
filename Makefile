build:
	@echo "Atualizando dependencias de build"
	python -m pip install -r requirements-build.txt
	@echo "Buildando aplicativo"
	python -m PyInstaller --noconfirm --clean AnalisadorDePlacas.spec