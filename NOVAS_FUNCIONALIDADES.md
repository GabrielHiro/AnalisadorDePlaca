# Novas Funcionalidades - AnalisadorDePlacas

## Implementadas

### 1. Atalhos de Teclado ⌨️

Acelera o processo de revisão sem necessidade de usar o mouse:

- **C** ou **Enter**: Marcar como Certo
- **F**: Marcar como Falha
- **O**: Marcar como Obstrução
- **S**: Pular imagem
- **V**: Alternar Veículo Especial
- **← →**: Navegar entre imagens (Anterior/Próxima)
- **1-9**: Selecionar classificação por índice
- **Ctrl+Z**: Desfazer última decisão
- **Ctrl+Y**: Refazer decisão desfeita
- **Ctrl+S**: Salvar sessão manualmente

### 2. Auto-Save de Sessão 💾

O sistema salva automaticamente o progresso:

- **Salvamento automático** a cada 5 decisões
- **Salvamento por tempo** a cada 2 minutos (120 segundos)
- **Arquivo**: `.session.json` na pasta de saída
- **Recuperação**: Ao iniciar análise, se existir sessão anterior, pergunta se deseja retomar

**Dados salvos**:
- Índice da imagem atual
- Decisões tomadas (ação, placa final, classificação, etc.)
- Timestamp do salvamento

### 3. Estatísticas em Tempo Real 📊

Painel de estatísticas na barra superior mostra:

- **Contadores**: ✓ Certas, ✗ Falhas, ⊘ Obstruções
- **Tempo médio** por imagem (baseado nas últimas 100 decisões)
- **Tempo restante estimado** (ETA) baseado no ritmo atual

**Exemplo**: `✓45 ✗12 ⊘3 | 1.8s/img | ~15min restantes`

### 4. Sistema de Undo/Redo ↶↷

- **Pilha de undo** armazena até 50 estados anteriores
- **Pilha de redo** permite refazer ações desfeitas
- **Estado salvo** antes de cada decisão ou pulo
- **Ctrl+Z** para desfazer, **Ctrl+Y** para refazer

### 5. Overlay de Placa Personalizável 🏷️

Sistema de overlay já existente com melhorias:

- **Exibição** da placa e classificação sobre a imagem
- **Tamanho de fonte** ajustável (16-72)
- **Opacidade** ajustável (0.2-1.0)
- **Posição** arrastável com o mouse
- **Botão Reset** para restaurar posição padrão

## Melhorias de Experiência

- **Painel de Atalhos** visível na interface mostrando comandos
- **Feedback visual** das decisões na lista de imagens
- **Persistência** de configurações durante a sessão
- **Proteção contra perda** de progresso

## Uso Recomendado

1. **Inicie a análise** selecionando pastas de origem e saída
2. Se houver **sessão anterior**, escolha retomar ou começar do zero
3. Use **atalhos de teclado** para máxima velocidade (3-5x mais rápido)
4. **Monitore estatísticas** para acompanhar progresso e tempo
5. O sistema **salva automaticamente** - não precisa se preocupar
6. Use **Ctrl+Z** se cometer algum erro
7. Ao finalizar, gere o **relatório** como de costume

## Arquivos Técnicos

- `ui/app.py`: Implementação principal das funcionalidades
- `.session.json`: Arquivo de sessão salvo na pasta de saída
- `test_new_features.py`: Testes unitários das novas funcionalidades

## Próximas Melhorias Sugeridas

- [ ] Filtros por classificação/ação na lista
- [ ] Modo de comparação lado a lado
- [ ] Histórico de alterações de placa
- [ ] Validação automática de formato de placa
- [ ] Exportação de relatório em múltiplos formatos
- [ ] Tema escuro/claro
- [ ] Busca por placa ou nome de arquivo
- [ ] Zoom com roda do mouse em área específica
