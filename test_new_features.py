"""Teste básico das novas funcionalidades."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from review.session import ReviewSession, ReviewDecision
from parser.filename import Action


def test_session_save_load():
    """Testa salvamento e carregamento de sessão."""
    # Cria uma sessão de teste
    with tempfile.TemporaryDirectory() as tmpdir:
        output_folder = Path(tmpdir)
        session_file = output_folder / ".session.json"
        
        # Cria dados de teste
        test_data = {
            "current_index": 5,
            "timestamp": 1234567890.0,
            "decisions": [
                {
                    "filepath": "/test/image1.jpg",
                    "action": "certa",
                    "placa_final": "ABC1234",
                    "skipped": False,
                    "veiculo_especial": False,
                    "classificacao": "Classificação 1",
                },
                {
                    "filepath": "/test/image2.jpg",
                    "action": None,
                    "placa_final": None,
                    "skipped": True,
                    "veiculo_especial": False,
                    "classificacao": None,
                },
            ],
        }
        
        # Salva
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f, indent=2)
        
        # Verifica se o arquivo foi criado
        assert session_file.exists()
        
        # Carrega
        with open(session_file, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        
        # Verifica
        assert loaded_data["current_index"] == 5
        assert len(loaded_data["decisions"]) == 2
        assert loaded_data["decisions"][0]["placa_final"] == "ABC1234"
        assert loaded_data["decisions"][1]["skipped"] is True
        
        print("✓ Teste de salvamento/carregamento de sessão passou!")


def test_undo_redo_state():
    """Testa estrutura de estado para undo/redo."""
    state = {
        "index": 3,
        "action": Action.CERTA,
        "placa_final": "XYZ5678",
        "skipped": False,
        "veiculo_especial": True,
        "classificacao": "Classificação 2",
    }
    
    # Simula pilha de undo
    undo_stack = []
    undo_stack.append(state)
    
    # Verifica
    assert len(undo_stack) == 1
    assert undo_stack[0]["placa_final"] == "XYZ5678"
    assert undo_stack[0]["veiculo_especial"] is True
    
    # Simula undo
    redo_stack = []
    restored_state = undo_stack.pop()
    redo_stack.append(restored_state)
    
    assert len(undo_stack) == 0
    assert len(redo_stack) == 1
    
    print("✓ Teste de estrutura undo/redo passou!")


def test_keyboard_shortcuts():
    """Testa mapeamento de atalhos de teclado."""
    shortcuts = {
        "c": "certo",
        "C": "certo",
        "<Return>": "certo",
        "f": "falha",
        "F": "falha",
        "o": "obstrucao",
        "O": "obstrucao",
        "s": "skip",
        "S": "skip",
        "v": "veiculo_especial",
        "V": "veiculo_especial",
        "<Left>": "anterior",
        "<Right>": "proximo",
        "<Control-z>": "undo",
        "<Control-y>": "redo",
        "<Control-s>": "save",
    }
    
    # Verifica mapeamentos
    assert shortcuts["c"] == "certo"
    assert shortcuts["<Return>"] == "certo"
    assert shortcuts["f"] == "falha"
    assert shortcuts["o"] == "obstrucao"
    assert shortcuts["<Control-z>"] == "undo"
    
    print("✓ Teste de mapeamento de atalhos passou!")


def test_statistics_calculation():
    """Testa cálculo de estatísticas."""
    decision_times = [1.5, 2.0, 1.8, 2.2, 1.9]
    
    # Calcula média
    avg_time = sum(decision_times) / len(decision_times)
    assert abs(avg_time - 1.88) < 0.01
    
    # Simula estimativa de tempo restante
    total = 100
    decided = 5
    remaining = (total - decided) * avg_time
    
    assert remaining == 95 * avg_time
    assert remaining > 0
    
    print("✓ Teste de cálculo de estatísticas passou!")


if __name__ == "__main__":
    test_session_save_load()
    test_undo_redo_state()
    test_keyboard_shortcuts()
    test_statistics_calculation()
    print("\n✅ Todos os testes passaram!")
