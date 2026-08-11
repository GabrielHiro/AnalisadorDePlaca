import importlib


def test_run_app_raises_clear_error_when_tkinter_is_unavailable(monkeypatch):
    module = importlib.import_module("ui.app")
    monkeypatch.setattr(module, "tk", None)

    try:
        module.run_app()
    except RuntimeError as exc:
        assert "Tkinter não está disponível" in str(exc)
    else:
        raise AssertionError("run_app deveria levantar RuntimeError quando Tkinter não estiver disponível")
