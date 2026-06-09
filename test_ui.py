#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script de teste para verificar se a UI inicia corretamente"""

try:
    print("Importando módulos...")
    import tkinter as tk
    from ui.app import AnalisadorApp
    
    print("Criando janela...")
    root = tk.Tk()
    
    print("Criando aplicação...")
    app = AnalisadorApp(root)
    
    print("Sucesso! A aplicação foi inicializada.")
    print("Fechando em 2 segundos...")
    root.after(2000, root.destroy)
    
    root.mainloop()
    
except Exception as e:
    print(f"\nERRO: {type(e).__name__}")
    print(f"Mensagem: {e}")
    import traceback
    print("\nStack trace completo:")
    traceback.print_exc()
