from ui.app import AnalisadorApp


def test_build_overlay_text_uses_plate_and_classification():
    app = AnalisadorApp.__new__(AnalisadorApp)
    text = app._build_overlay_text("ABC1234", "Classificação 2")
    assert text == "PLACA: ABC1234\nClassificação: Classificação 2"
