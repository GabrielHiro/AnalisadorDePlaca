from __future__ import annotations

import json
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # pragma: no cover - ambiente sem Tkinter
    tk = None
    filedialog = None
    messagebox = None
    ttk = None

from PIL import Image, ImageDraw, ImageFont

try:
    from PIL import ImageTk
except ImportError:  # pragma: no cover - fallback para ambientes sem Tkinter
    ImageTk = None

from organizer.folders import build_analysis_summary, organize_single, write_report
from parser.filename import (
    Action,
    build_output_filename,
    format_horario_display,
    resolve_placa_for_action,
    validate_placa,
)
from parser.image_metadata import (
    CLASSIFICACAO_BY_ID,
    classificacao_option_label,
    format_classificacao,
    parse_input_image,
)
from review.session import ReviewDecision, ReviewSession, build_decisions, scan_image_files


class AnalisadorApp:
    ZOOM_MIN = 0.5
    ZOOM_MAX = 4.0
    ZOOM_STEP = 1.1

    def __init__(self, root: object) -> None:
        if tk is None or ttk is None or filedialog is None or messagebox is None:
            raise RuntimeError("Tkinter não está disponível neste ambiente.")
        self.root = root
        self.root.title("Analisador de Placas")
        self.root.geometry("1280x760")
        self.root.minsize(1180, 640)

        self.session = ReviewSession()
        self._current_pil_image: Image.Image | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_data: dict[str, int] | None = None
        self._analysis_started = False
        self._source_folder: Path | None = None
        self._output_folder: Path | None = None
        self._updating_list = False
        self._overlay_text = ""
        self._overlay_font_size = 32
        self._overlay_opacity = 0.82
        self._overlay_position = (0.12, 0.10)
        self._overlay_photo: ImageTk.PhotoImage | None = None
        self._overlay_drag_data: dict[str, float] | None = None
        self._auto_save_counter = 0
        self._last_save_time = 0
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._stats_start_time = time.time()
        self._decision_times: list[float] = []

        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._refresh_view()
        self._try_load_session()

    def _build_ui(self) -> None:
        setup_frame = ttk.LabelFrame(self.root, text="Configuração inicial", padding=8)
        setup_frame.pack(fill=tk.X, padx=8, pady=(8, 0))

        source_row = ttk.Frame(setup_frame)
        source_row.pack(fill=tk.X, pady=2)
        ttk.Label(source_row, text="Pasta de origem:", width=16).pack(side=tk.LEFT)
        self.source_folder_label = ttk.Label(
            source_row,
            text="Não selecionada",
            foreground="#555",
        )
        self.source_folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            source_row,
            text="Escolher origem",
            command=self._choose_source_folder,
        ).pack(side=tk.RIGHT)

        output_row = ttk.Frame(setup_frame)
        output_row.pack(fill=tk.X, pady=2)
        ttk.Label(output_row, text="Pasta de saída:", width=16).pack(side=tk.LEFT)
        self.output_folder_label = ttk.Label(
            output_row,
            text="Não selecionada",
            foreground="#555",
        )
        self.output_folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            output_row,
            text="Escolher saída",
            command=self._choose_output_folder,
        ).pack(side=tk.RIGHT)

        action_row = ttk.Frame(setup_frame)
        action_row.pack(fill=tk.X, pady=(8, 0))
        self.start_button = ttk.Button(
            action_row,
            text="Iniciar análise",
            command=self._start_analysis,
            state=tk.DISABLED,
        )
        self.start_button.pack(side=tk.LEFT)
        ttk.Label(
            action_row,
            text="Escolha origem e saída antes de revisar as imagens.",
            foreground="#555",
        ).pack(side=tk.LEFT, padx=12)

        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill=tk.X)

        self.progress_label = ttk.Label(toolbar, text="0 / 0")
        self.progress_label.pack(side=tk.LEFT, padx=12)

        self.progress_bar = ttk.Progressbar(toolbar, length=220, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, padx=8)

        zoom_frame = ttk.Frame(toolbar)
        zoom_frame.pack(side=tk.LEFT, padx=8)
        ttk.Button(zoom_frame, text="-", width=3, command=self._zoom_out).pack(
            side=tk.LEFT
        )
        self.zoom_label = ttk.Label(zoom_frame, text="100%", width=6, anchor=tk.CENTER)
        self.zoom_label.pack(side=tk.LEFT, padx=4)
        ttk.Button(zoom_frame, text="+", width=3, command=self._zoom_in).pack(
            side=tk.LEFT
        )
        ttk.Button(zoom_frame, text="Ajustar", command=self._zoom_reset).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        self.finish_button = ttk.Button(
            toolbar,
            text="Gerar relatório",
            command=self._finish_batch,
            state=tk.DISABLED,
        )
        self.finish_button.pack(side=tk.RIGHT)

        stats_frame = ttk.Frame(toolbar)
        stats_frame.pack(side=tk.RIGHT, padx=(16, 0))
        self.stats_label = ttk.Label(stats_frame, text="", foreground="#666")
        self.stats_label.pack(side=tk.LEFT)

        content = ttk.Frame(self.root, padding=8)
        content.pack(fill=tk.BOTH, expand=True)
        self.content_frame = content

        list_frame = ttk.LabelFrame(content, text="Imagens", padding=8)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 8))
        list_frame.pack_propagate(False)
        list_frame.config(width=260)

        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.image_tree = ttk.Treeview(
            list_container,
            columns=("num", "arquivo", "status"),
            show="headings",
            selectmode="browse",
        )
        self.image_tree.heading("num", text="#")
        self.image_tree.heading("arquivo", text="Arquivo")
        self.image_tree.heading("status", text="Status")
        
        self.image_tree.column("num", width=40, anchor=tk.CENTER)
        self.image_tree.column("arquivo", width=120)
        self.image_tree.column("status", width=80)

        self.image_tree.tag_configure("current", background="#e6f3ff")
        self.image_tree.tag_configure("certo", foreground="#16a34a")
        self.image_tree.tag_configure("falha", foreground="#dc2626")
        self.image_tree.tag_configure("obstruida", foreground="#ea580c")
        self.image_tree.tag_configure("pulado", foreground="#64748b")
        self.image_tree.tag_configure("invalido", foreground="#ef4444")
        self.image_tree.tag_configure("pendente", foreground="#475569")

        tree_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.image_tree.yview)
        self.image_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.image_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.image_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.image_frame = ttk.LabelFrame(content, text="Imagem", padding=8)
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.image_canvas = tk.Canvas(
            self.image_frame,
            highlightthickness=0,
            bg="#1e1e1e",
        )
        self.overlay_controls = ttk.Frame(self.image_frame)
        self.overlay_controls.pack(fill=tk.X, pady=(0, 6))

        self.overlay_size_var = tk.IntVar(value=self._overlay_font_size)
        self.overlay_opacity_var = tk.DoubleVar(value=self._overlay_opacity)

        ttk.Label(self.overlay_controls, text="Overlay").pack(side=tk.LEFT)
        ttk.Label(self.overlay_controls, text="Tamanho").pack(side=tk.LEFT, padx=(8, 4))
        ttk.Scale(
            self.overlay_controls,
            from_=16,
            to=72,
            variable=self.overlay_size_var,
            orient=tk.HORIZONTAL,
            length=120,
            command=lambda _value: self._update_overlay_from_controls(),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(self.overlay_controls, text="Opacidade").pack(side=tk.LEFT)
        ttk.Scale(
            self.overlay_controls,
            from_=0.2,
            to=1.0,
            variable=self.overlay_opacity_var,
            orient=tk.HORIZONTAL,
            length=120,
            command=lambda _value: self._update_overlay_from_controls(),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            self.overlay_controls,
            text="Resetar posição",
            command=self._reset_overlay_position,
        ).pack(side=tk.RIGHT)

        self.image_canvas.pack(fill=tk.BOTH, expand=True)
        self.image_canvas.bind("<MouseWheel>", self._on_image_wheel)
        self.image_canvas.bind("<ButtonPress-1>", self._on_image_drag_start)
        self.image_canvas.bind("<B1-Motion>", self._on_image_drag_move)
        self.image_canvas.bind("<ButtonRelease-1>", self._on_image_drag_end)
        self.image_canvas.tag_bind("overlay", "<ButtonPress-1>", self._on_overlay_drag_start)
        self.image_canvas.tag_bind("overlay", "<B1-Motion>", self._on_overlay_drag_move)
        self.image_canvas.tag_bind("overlay", "<ButtonRelease-1>", self._on_overlay_drag_end)
        self.image_frame.bind("<Configure>", self._on_image_frame_resize)

        side = ttk.Frame(content, padding=(8, 0, 0, 0), width=320)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)

        actions_frame = ttk.LabelFrame(side, text="Ações", padding=8)
        actions_frame.pack(fill=tk.X, side=tk.TOP)

        self.certa_button = ttk.Button(
            actions_frame,
            text="Certo",
            command=self._apply_certo,
        )
        self.certa_button.pack(fill=tk.X, pady=2)

        self.errada_button = ttk.Button(
            actions_frame,
            text="Falha técnica",
            command=lambda: self._apply_action(Action.ERRADA),
        )
        self.errada_button.pack(fill=tk.X, pady=2)

        self.obstrucao_button = ttk.Button(
            actions_frame,
            text="Obstrução",
            command=lambda: self._apply_action(Action.OBSTRUCAO),
        )
        self.obstrucao_button.pack(fill=tk.X, pady=2)

        self.veiculo_especial_var = tk.BooleanVar(value=False)
        self.veiculo_especial_check = ttk.Checkbutton(
            actions_frame,
            text="Veículo especial",
            variable=self.veiculo_especial_var,
        )
        self.veiculo_especial_check.pack(fill=tk.X, pady=2)

        classif_frame = ttk.Frame(actions_frame)
        classif_frame.pack(fill=tk.X, pady=(6, 2))
        ttk.Label(classif_frame, text="Classificação:").pack(anchor=tk.W)
        self.classificacao_var = tk.StringVar()
        self.classificacao_combo = ttk.Combobox(
            classif_frame,
            textvariable=self.classificacao_var,
            state="readonly",
            values=[
                classificacao_option_label(cid) for cid in CLASSIFICACAO_BY_ID
            ],
        )
        self.classificacao_combo.pack(fill=tk.X, pady=(2, 0))
        self.classificacao_combo.set(classificacao_option_label(0))
        self.classificacao_combo.bind(
            "<<ComboboxSelected>>", self._update_output_preview
        )

        manual_frame = ttk.LabelFrame(
            actions_frame,
            text="Placa correta (opcional)",
            padding=6,
        )
        manual_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(
            manual_frame,
            text="Preencha se corrigiu a placa (Certo ou Falha técnica). Vazio = usa a detectada.",
            wraplength=280,
            foreground="#555",
        ).pack(anchor=tk.W, pady=(0, 4))

        self.manual_entry = ttk.Entry(manual_frame, font=("Segoe UI", 11))
        self.manual_entry.pack(fill=tk.X, pady=(0, 4))
        self.manual_entry.bind("<KeyRelease>", self._update_output_preview)

        nav_frame = ttk.Frame(side)
        nav_frame.pack(fill=tk.X, side=tk.TOP, pady=(8, 0))

        self.prev_button = ttk.Button(
            nav_frame,
            text="Anterior",
            command=self._go_previous,
            state=tk.DISABLED,
        )
        self.prev_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.next_button = ttk.Button(
            nav_frame,
            text="Próxima",
            command=self._go_next,
            state=tk.DISABLED,
        )
        self.next_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.skip_button = ttk.Button(
            side,
            text="Pular arquivo inválido",
            command=self._skip_current,
        )
        self.skip_button.pack(fill=tk.X, side=tk.TOP, pady=(8, 0))

        meta_scroll_frame = ttk.Frame(side)
        meta_scroll_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP, pady=(8, 0))

        meta_canvas = tk.Canvas(
            meta_scroll_frame,
            highlightthickness=0,
            borderwidth=0,
        )
        meta_scrollbar = ttk.Scrollbar(
            meta_scroll_frame,
            orient=tk.VERTICAL,
            command=meta_canvas.yview,
        )
        meta_canvas.configure(yscrollcommand=meta_scrollbar.set)
        meta_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        meta_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        meta_inner = ttk.Frame(meta_canvas)
        meta_window = meta_canvas.create_window((0, 0), window=meta_inner, anchor=tk.NW)

        def _on_meta_configure(_event) -> None:
            meta_canvas.configure(scrollregion=meta_canvas.bbox("all"))

        def _on_meta_canvas_configure(event) -> None:
            meta_canvas.itemconfigure(meta_window, width=event.width)

        meta_inner.bind("<Configure>", _on_meta_configure)
        meta_canvas.bind("<Configure>", _on_meta_canvas_configure)

        def _on_meta_mousewheel(event) -> None:
            meta_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        meta_canvas.bind("<Enter>", lambda _e: meta_canvas.bind_all("<MouseWheel>", _on_meta_mousewheel))
        meta_canvas.bind("<Leave>", lambda _e: meta_canvas.unbind_all("<MouseWheel>"))

        meta_frame = ttk.LabelFrame(meta_inner, text="Metadados", padding=8)
        meta_frame.pack(fill=tk.X)

        self.meta_labels: dict[str, ttk.Label] = {}
        for key, title in [
            ("arquivo", "Arquivo"),
            ("equipamento", "Equipamento"),
            ("faixa", "Faixa"),
            ("sentido", "Sentido"),
            ("periodo", "Período"),
            ("horario", "Horário"),
            ("placa", "Placa detectada"),
            ("classificacao", "Classificação"),
            ("nome_saida", "Nome de saída"),
            ("decisao", "Decisão atual"),
        ]:
            row = ttk.Frame(meta_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{title}:", width=16).pack(side=tk.LEFT)
            label = ttk.Label(row, text="-", wraplength=240)
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.meta_labels[key] = label

        self.warning_label = ttk.Label(
            meta_inner,
            text="",
            foreground="#b45309",
            wraplength=260,
        )
        self.warning_label.pack(fill=tk.X, pady=(8, 0))

        shortcuts_frame = ttk.LabelFrame(meta_inner, text="Atalhos", padding=8)
        shortcuts_frame.pack(fill=tk.X, pady=(8, 0))
        shortcuts_text = (
            "C/Enter: Certo  |  F: Falha  |  O: Obstrução\n"
            "S: Pular  |  V: Veículo Especial  |  ←→: Navegar\n"
            "1-9: Classificação  |  Ctrl+Z: Desfazer  |  Ctrl+S: Salvar"
        )
        ttk.Label(shortcuts_frame, text=shortcuts_text, foreground="#555", font=("Segoe UI", 8)).pack()

        self._set_review_enabled(False)

    def _choose_source_folder(self) -> None:
        if self._analysis_started:
            return

        folder = filedialog.askdirectory(
            title="Selecionar pasta de origem (busca em subpastas)",
        )
        if not folder:
            return

        self._source_folder = Path(folder)
        self.source_folder_label.config(text=str(self._source_folder))
        self._update_start_button()

    def _choose_output_folder(self) -> None:
        if self._analysis_started:
            return

        initial = str(self._source_folder) if self._source_folder else None
        folder = filedialog.askdirectory(
            title="Selecionar pasta de saída",
            initialdir=initial,
        )
        if not folder:
            return

        self._output_folder = Path(folder)
        self.output_folder_label.config(text=str(self._output_folder))
        self._update_start_button()

    def _update_start_button(self) -> None:
        ready = (
            not self._analysis_started
            and self._source_folder is not None
            and self._output_folder is not None
        )
        self.start_button.config(state=tk.NORMAL if ready else tk.DISABLED)

    def _start_analysis(self) -> None:
        if self._source_folder is None or self._output_folder is None:
            messagebox.showwarning(
                "Configuração incompleta",
                "Selecione a pasta de origem e a pasta de saída.",
            )
            return

        self.start_button.config(state=tk.DISABLED)

        modal = tk.Toplevel(self.root)
        modal.title("Carregando")
        modal.geometry("400x120")
        modal.resizable(False, False)
        modal.transient(self.root)
        modal.grab_set()

        center_x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        center_y = self.root.winfo_y() + (self.root.winfo_height() - 120) // 2
        modal.geometry(f"+{center_x}+{center_y}")

        ttk.Label(modal, text="Carregando imagens...", font=("Segoe UI", 11)).pack(pady=(20, 10))
        
        progress = ttk.Progressbar(modal, length=350, mode="determinate")
        progress.pack(pady=10)
        
        progress_label = ttk.Label(modal, text="0 / 0")
        progress_label.pack()

        def load_thread():
            try:
                files = scan_image_files(self._source_folder)
                
                if len(files) == 0:
                    self.root.after(0, lambda: self._on_load_empty(modal))
                    return

                total = len(files)
                self.root.after(
                    0,
                    lambda t=total: self._update_progress(
                        progress, progress_label, 0, t
                    ),
                )

                decisions = []
                invalid_count = 0

                for i, filepath in enumerate(files):
                    parsed = parse_input_image(filepath)
                    if not parsed.valid:
                        invalid_count += 1

                    decisions.append(
                        ReviewDecision(
                            filepath=filepath,
                            parsed=parsed,
                        )
                    )

                    current = i + 1
                    self.root.after(
                        0,
                        lambda c=current, t=total: self._update_progress(
                            progress, progress_label, c, t
                        ),
                    )
                
                self.root.after(0, lambda: self._on_load_complete(
                    modal, decisions, invalid_count
                ))
                
            except Exception as e:
                self.root.after(0, lambda: self._on_load_error(modal, str(e)))

        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()

    def _update_progress(self, progress, label, current, total):
        progress["maximum"] = total
        progress["value"] = current
        label.config(text=f"{current} / {total}")

    def _on_load_empty(self, modal):
        modal.destroy()
        messagebox.showinfo(
            "Pasta vazia",
            "Nenhuma imagem JPG encontrada na pasta de origem ou subpastas.",
        )
        self._update_start_button()

    def _on_load_error(self, modal, error):
        modal.destroy()
        messagebox.showerror("Erro ao carregar", f"Erro durante o carregamento: {error}")
        self._update_start_button()

    def _on_load_complete(self, modal, decisions, invalid_count):
        modal.destroy()
        
        self.session.source_folder = self._source_folder
        self.session.output_folder = self._output_folder
        self.session.decisions = decisions
        self.session.current_index = 0
        self.session.processed_paths.clear()
        self.session.process_errors.clear()

        self._analysis_started = True
        self.start_button.config(state=tk.DISABLED)
        self._set_review_enabled(True)

        if invalid_count:
            messagebox.showwarning(
                "Arquivos inválidos",
                f"{invalid_count} arquivo(s) com nome inválido podem ser pulados.",
            )

        self._clear_manual_entry()
        self._refresh_view()

    def _clear_manual_entry(self) -> None:
        self.manual_entry.delete(0, tk.END)

    def _get_status_text(self, decision) -> tuple[str, str]:
        if not decision.parsed.valid:
            return "Inválido", "invalido"
        if decision.skipped:
            return "Pulado", "pulado"
        if decision.action == Action.CERTA:
            if decision.veiculo_especial:
                return "Certo (VE)", "certo"
            return "Certo", "certo"
        if decision.action == Action.ERRADA:
            if decision.veiculo_especial:
                return "Falha (VE)", "falha"
            return "Falha técnica", "falha"
        if decision.action == Action.OBSTRUCAO:
            return "Obstruída", "obstruida"
        return "Pendente", "pendente"

    def _refresh_image_list(self) -> None:
        if self._updating_list:
            return
        
        self._updating_list = True
        
        for item in self.image_tree.get_children():
            self.image_tree.delete(item)
        
        for i, decision in enumerate(self.session.decisions):
            status_text, status_tag = self._get_status_text(decision)
            filename = decision.filepath.name
            if len(filename) > 30:
                filename = filename[:27] + "..."
            
            tags = [status_tag]
            if i == self.session.current_index:
                tags.append("current")
            
            self.image_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(str(i + 1), filename, status_text),
                tags=tags,
            )
        
        if self.session.current_index >= 0 and self.session.current_index < len(self.session.decisions):
            current_iid = str(self.session.current_index)
            self.image_tree.selection_set(current_iid)
            self.image_tree.see(current_iid)
        
        self._updating_list = False

    def _on_tree_select(self, event) -> None:
        if self._updating_list or not self._analysis_started:
            return
        
        selection = self.image_tree.selection()
        if not selection:
            return
        
        try:
            index = int(selection[0])
            if index != self.session.current_index:
                self.session.go_to(index)
                self._refresh_view()
        except (ValueError, IndexError):
            pass

    def _set_review_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for widget in (
            self.certa_button,
            self.errada_button,
            self.veiculo_especial_check,
            self.obstrucao_button,
            self.manual_entry,
            self.prev_button,
            self.next_button,
            self.skip_button,
        ):
            widget.config(state=state)
        self.classificacao_combo.config(
            state="readonly" if enabled else tk.DISABLED
        )
        if not enabled:
            self.finish_button.config(state=tk.DISABLED)
        else:
            self.finish_button.config(state=tk.NORMAL)

    def _refresh_view(self) -> None:
        current = self.session.current
        total = self.session.total
        decided = self.session.decided_count
        current_pos = self.session.current_index + 1 if total > 0 else 0

        self.progress_label.config(text=f"Imagem {current_pos} / {total} · {decided} classificadas")
        self.progress_bar.config(maximum=max(total, 1), value=decided)

        self.prev_button.config(
            state=tk.NORMAL if self.session.current_index > 0 else tk.DISABLED
        )
        self.next_button.config(
            state=tk.NORMAL
            if total > 0 and self.session.current_index < total - 1
            else tk.DISABLED
        )

        if current is None:
            self._clear_image()
            for label in self.meta_labels.values():
                label.config(text="-")
            if not self._analysis_started:
                self.warning_label.config(
                    text="Configure origem e saída, depois clique em Iniciar análise."
                )
            else:
                self.warning_label.config(text="")
            self._set_action_state(tk.DISABLED)
            return

        self._refresh_overlay_text(current)
        self._show_image(current.filepath)
        parsed = current.parsed

        periodo_label = (
            f"{parsed.periodo} ({parsed.periodo_folder})"
            if parsed.valid
            else "-"
        )
        decisao = "-"
        if current.skipped:
            decisao = "Pulado"
        elif current.action:
            action_labels = {
                Action.CERTA: "certo",
                Action.ERRADA: "falha tecnica",
                Action.OBSTRUCAO: "obstruida",
            }
            decisao = action_labels.get(current.action, current.action.value)
            if current.veiculo_especial:
                decisao += " (veiculo especial)"
            if current.placa_final:
                decisao += f" -> {current.placa_final}"

        if current.action:
            self.veiculo_especial_var.set(current.veiculo_especial)
        else:
            self.veiculo_especial_var.set(False)

        selected_id = (
            current.classificacao
            if current.classificacao is not None
            else parsed.id_final
        )
        if selected_id not in CLASSIFICACAO_BY_ID:
            selected_id = 0
        self.classificacao_var.set(classificacao_option_label(selected_id))

        self.meta_labels["arquivo"].config(text=current.filepath.name)
        self.meta_labels["equipamento"].config(text=parsed.n_serie or "-")
        self.meta_labels["faixa"].config(text=parsed.faixa or "-")
        self.meta_labels["sentido"].config(text=parsed.sentido or "-")
        self.meta_labels["periodo"].config(text=periodo_label)
        self.meta_labels["horario"].config(
            text=format_horario_display(parsed.horario) if parsed.horario else "-"
        )
        self.meta_labels["placa"].config(text=parsed.placa_detectada or "-")
        self.meta_labels["classificacao"].config(
            text=format_classificacao(parsed.id_final)
        )
        self.meta_labels["nome_saida"].config(
            text=self._current_output_name(current) or "-"
        )
        self.meta_labels["decisao"].config(text=decisao)

        if not parsed.valid:
            self.warning_label.config(
                text=parsed.error or "Nome de arquivo invalido."
            )
            self._set_action_state(tk.DISABLED)
        elif parsed.sentido == "DESCONHECIDO":
            self.warning_label.config(
                text="Sentido nao encontrado no nome. Sera usado DESCONHECIDO."
            )
            self._set_action_state(tk.NORMAL)
        else:
            self.warning_label.config(text="")
            self._set_action_state(tk.NORMAL)

        if current.action == Action.CERTA and current.placa_final:
            if current.placa_final != parsed.placa_detectada:
                self.manual_entry.delete(0, tk.END)
                self.manual_entry.insert(0, current.placa_final)
        elif not current.action:
            self._clear_manual_entry()

        self._refresh_image_list()

    def _preview_placa_for_certo(self, current) -> str | None:
        manual = self.manual_entry.get().strip()
        placa_final, error = resolve_placa_for_action(
            current.parsed,
            Action.CERTA,
            manual or None,
        )
        if error or placa_final is None:
            return None
        return placa_final

    def _id_final_for_output(self, current) -> int:
        if current.classificacao is not None:
            return current.classificacao
        return self._selected_classificacao()

    def _current_output_name(self, current) -> str | None:
        id_final = self._id_final_for_output(current)
        if current.placa_final:
            return build_output_filename(
                current.parsed, current.placa_final, id_final=id_final
            )

        if current.parsed.valid:
            placa = self._preview_placa_for_certo(current)
            if placa:
                return build_output_filename(
                    current.parsed, placa, id_final=id_final
                )
        return None

    def _update_output_preview(self, _event=None) -> None:
        current = self.session.current
        if current is None or not current.parsed.valid:
            return
        preview = self._current_output_name(current)
        self.meta_labels["nome_saida"].config(text=preview or "-")
        self._refresh_overlay_text(self.session.current)

    def _set_action_state(self, state: str) -> None:
        if not self._analysis_started:
            state = tk.DISABLED
        self.certa_button.config(state=state)
        self.errada_button.config(state=state)
        self.veiculo_especial_check.config(state=state)
        self.classificacao_combo.config(
            state="readonly" if state == tk.NORMAL else tk.DISABLED
        )
        self.obstrucao_button.config(state=state)
        self.manual_entry.config(state=state)

    def _clear_image(self) -> None:
        self._current_pil_image = None
        self._photo = None
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_data = None
        self._overlay_photo = None
        self.image_canvas.delete("all")
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        self.zoom_label.config(text=f"{int(self._zoom_level * 100)}%")

    def _build_overlay_text(self, placa: str, classificacao: str) -> str:
        return f"PLACA: {placa or '-'}\nClassificação: {classificacao or '-'}"

    def _refresh_overlay_text(self, current) -> None:
        if current is None:
            self._overlay_text = ""
            self._render_overlay()
            return

        parsed = current.parsed
        selected_id = (
            current.classificacao
            if current.classificacao is not None
            else self._selected_classificacao()
        )
        if selected_id not in CLASSIFICACAO_BY_ID:
            selected_id = 0

        self._overlay_text = self._build_overlay_text(
            parsed.placa_detectada or "-",
            format_classificacao(selected_id),
        )
        self._render_overlay()

    def _update_overlay_from_controls(self) -> None:
        self._overlay_font_size = max(16, int(self.overlay_size_var.get()))
        self._overlay_opacity = max(0.2, min(1.0, float(self.overlay_opacity_var.get())))
        if self._current_pil_image is not None:
            self._render_image()
        else:
            self._render_overlay()

    def _reset_overlay_position(self) -> None:
        self._overlay_position = (0.12, 0.10)
        self._render_image()

    def _load_overlay_font(self, font_size: int) -> ImageFont.ImageFont:
        for candidate in ("DejaVuSans-Bold.ttf", "arial.ttf", "Arial.ttf"):
            try:
                return ImageFont.truetype(candidate, font_size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _render_overlay(self) -> None:
        self.image_canvas.delete("overlay")
        if self._current_pil_image is None or not self._overlay_text:
            self._overlay_photo = None
            return

        canvas_w = max(1, self.image_canvas.winfo_width())
        canvas_h = max(1, self.image_canvas.winfo_height())
        font_size = max(16, self._overlay_font_size)
        font = self._load_overlay_font(font_size)

        lines = [line.strip() for line in self._overlay_text.splitlines() if line.strip()]
        if not lines:
            self._overlay_photo = None
            return

        dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        line_widths = []
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        text_width = max(line_widths) if line_widths else 1
        text_height = sum(line_heights) + max(8, font_size // 3) * (len(lines) - 1)
        padding_x = max(18, int(canvas_w * 0.03))
        padding_y = max(16, int(canvas_h * 0.03))
        box_w = text_width + padding_x * 2
        box_h = text_height + padding_y * 2

        overlay = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(overlay)
        panel_draw.rounded_rectangle(
            [(0, 0), (box_w - 1, box_h - 1)],
            radius=max(16, font_size // 2),
            fill=(0, 0, 0, int(160 * self._overlay_opacity)),
            outline=(255, 255, 255, int(60 * self._overlay_opacity)),
        )

        y = padding_y
        for line in lines:
            bbox = panel_draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            panel_draw.text((padding_x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
            panel_draw.text((padding_x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_height + max(8, font_size // 3)

        self._overlay_photo = ImageTk.PhotoImage(overlay)
        x = int(self._overlay_position[0] * canvas_w)
        y = int(self._overlay_position[1] * canvas_h)
        x = max(0, min(canvas_w - overlay.width, x))
        y = max(0, min(canvas_h - overlay.height, y))
        self.image_canvas.create_image(x, y, image=self._overlay_photo, anchor="nw", tags=("overlay",))

    def _zoom_in(self) -> None:
        if self._current_pil_image is None:
            return
        self._zoom_level = min(self.ZOOM_MAX, self._zoom_level * self.ZOOM_STEP)
        self._render_image()

    def _zoom_out(self) -> None:
        if self._current_pil_image is None:
            return
        self._zoom_level = max(self.ZOOM_MIN, self._zoom_level / self.ZOOM_STEP)
        if self._zoom_level <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        self._render_image()

    def _zoom_reset(self) -> None:
        if self._current_pil_image is None:
            return
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._render_image()

    def _on_image_wheel(self, event) -> None:
        if self._current_pil_image is None:
            return
        if event.delta > 0:
            self._zoom_level = min(self.ZOOM_MAX, self._zoom_level * self.ZOOM_STEP)
        else:
            self._zoom_level = max(self.ZOOM_MIN, self._zoom_level / self.ZOOM_STEP)
            if self._zoom_level <= 1.0:
                self._pan_x = 0
                self._pan_y = 0
        self._render_image()

    def _on_image_drag_start(self, event) -> None:
        if self._current_pil_image is None or self._zoom_level <= 1.0:
            return
        if self.image_canvas.find_withtag("current") and "overlay" in self.image_canvas.gettags("current"):
            return
        self._drag_data = {"x": event.x, "y": event.y}

    def _on_image_drag_move(self, event) -> None:
        if self._drag_data is None:
            return
        self._pan_x += event.x - self._drag_data["x"]
        self._pan_y += event.y - self._drag_data["y"]
        self._drag_data = {"x": event.x, "y": event.y}
        self._render_image()

    def _on_image_drag_end(self, _event) -> None:
        self._drag_data = None

    def _on_overlay_drag_start(self, event) -> None:
        self._overlay_drag_data = {
            "x": event.x,
            "y": event.y,
            "px": self._overlay_position[0],
            "py": self._overlay_position[1],
        }

    def _on_overlay_drag_move(self, event) -> None:
        if self._overlay_drag_data is None:
            return
        canvas_w = max(1, self.image_canvas.winfo_width())
        canvas_h = max(1, self.image_canvas.winfo_height())
        delta_x = (event.x - self._overlay_drag_data["x"]) / canvas_w
        delta_y = (event.y - self._overlay_drag_data["y"]) / canvas_h
        x = self._overlay_drag_data["px"] + delta_x
        y = self._overlay_drag_data["py"] + delta_y
        self._overlay_position = (max(0.0, min(1.0, x)), max(0.0, min(1.0, y)))
        self._render_overlay()

    def _on_overlay_drag_end(self, _event) -> None:
        self._overlay_drag_data = None

    def _on_image_frame_resize(self, _event) -> None:
        if self._current_pil_image is not None:
            self._render_image()

    def _render_image(self) -> None:
        if self._current_pil_image is None:
            return

        canvas_w = self.image_canvas.winfo_width()
        canvas_h = self.image_canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            self.root.after(50, self._render_image)
            return

        img_w, img_h = self._current_pil_image.size
        fit_scale = min(canvas_w / img_w, canvas_h / img_h)
        scale = fit_scale * self._zoom_level
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        resized = self._current_pil_image.resize(
            (new_w, new_h),
            Image.Resampling.LANCZOS,
        )
        self._photo = ImageTk.PhotoImage(resized)

        self.image_canvas.delete("all")
        x = canvas_w // 2 + self._pan_x
        y = canvas_h // 2 + self._pan_y
        self.image_canvas.create_image(x, y, image=self._photo, anchor=tk.CENTER)
        self._render_overlay()
        self._update_zoom_label()

    def _show_image(self, filepath: Path) -> None:
        try:
            with Image.open(filepath) as image:
                self._current_pil_image = image.convert("RGB")
            self._zoom_level = 1.0
            self._pan_x = 0
            self._pan_y = 0
            self._drag_data = None
            self._render_image()
        except OSError:
            self._clear_image()
            canvas_w = max(self.image_canvas.winfo_width(), 200)
            canvas_h = max(self.image_canvas.winfo_height(), 100)
            self.image_canvas.create_text(
                canvas_w // 2,
                canvas_h // 2,
                text=f"Erro ao abrir: {filepath.name}",
                fill="white",
            )

    def _apply_certo(self) -> None:
        if not self._analysis_started:
            return

        current = self.session.current
        if current is None or not current.parsed.valid:
            return

        manual_placa = self.manual_entry.get().strip() or None
        placa_final, error = resolve_placa_for_action(
            current.parsed,
            Action.CERTA,
            manual_placa,
        )
        if error or placa_final is None:
            messagebox.showerror("Placa invalida", error or "Nao foi possivel confirmar.")
            return

        self._finalize_decision(Action.CERTA, placa_final)

    def _apply_action(self, action: Action) -> None:
        if not self._analysis_started:
            return
        current = self.session.current
        if current is None or not current.parsed.valid:
            return

        manual_placa = self.manual_entry.get().strip() or None
        placa_final, error = resolve_placa_for_action(
            current.parsed,
            action,
            manual_placa,
        )
        if error or placa_final is None:
            messagebox.showerror("Erro", error or "Nao foi possivel aplicar a acao.")
            return

        self._finalize_decision(action, placa_final)

    def _veiculo_especial_for_action(self, action: Action) -> bool:
        if action == Action.OBSTRUCAO:
            return False
        return self.veiculo_especial_var.get()

    def _selected_classificacao(self) -> int:
        raw = self.classificacao_var.get().split("-", 1)[0].strip()
        try:
            value = int(raw)
        except ValueError:
            return 0
        if value not in CLASSIFICACAO_BY_ID:
            return 0
        return value

    def _finalize_decision(self, action: Action, placa_final: str) -> None:
        veiculo_especial = self._veiculo_especial_for_action(action)
        self.session.set_decision(
            action,
            placa_final,
            veiculo_especial=veiculo_especial,
            classificacao=self._selected_classificacao(),
        )
        self._clear_manual_entry()
        self._process_current_decision(action, placa_final)

        if self.session.current_index < self.session.total - 1:
            self.session.go_next()

        self._refresh_view()

    def _process_current_decision(self, action: Action, placa_final: str) -> None:
        current = self.session.current
        if current is None or self.session.output_folder is None:
            return

        target, error = organize_single(current, self.session.output_folder)
        if error or target is None:
            current.action = None
            current.placa_final = None
            current.veiculo_especial = False
            current.classificacao = None
            messagebox.showerror(
                "Erro ao copiar",
                error or "Nao foi possivel copiar a imagem.",
            )
            self.session.process_errors.append(
                f"{current.parsed.source_name}: {error}"
            )
            return

        self.session.processed_paths = [
            entry
            for entry in self.session.processed_paths
            if entry[0] != current.parsed.source_name
        ]
        self.session.processed_paths.append(
            (current.parsed.source_name, str(target))
        )

    def _skip_current(self) -> None:
        current = self.session.current
        if current is None:
            return

        self.session.skip_current()
        self._clear_manual_entry()

        if self.session.current_index < self.session.total - 1:
            self.session.go_next()

        self._refresh_view()

    def _go_previous(self) -> None:
        self.session.go_previous()
        self._refresh_view()

    def _go_next(self) -> None:
        self.session.go_next()
        self._refresh_view()

    def _finish_batch(self) -> None:
        if not self._analysis_started:
            return

        if self.session.output_folder is None:
            messagebox.showerror("Erro", "Pasta de saida nao definida.")
            return

        summary = build_analysis_summary(self.session.decisions)
        if summary.quantidade_analisada == 0:
            messagebox.showinfo(
                "Nada para relatar",
                "Nenhuma imagem foi classificada ainda.",
            )
            return

        report_path = write_report(summary, self.session.output_folder)
        error_count = len(self.session.process_errors)

        summary_text = (
            f"Quantidade analisada: {summary.quantidade_analisada}\n"
            f"Placas corretas: {summary.placas_corretas}\n"
            f"Falhas tecnicas: {summary.falhas_tecnicas}\n"
            f"Falhas por obstrucao: {summary.falhas_obstrucao}\n\n"
            f"Relatorio: {report_path}"
        )

        if error_count:
            messagebox.showwarning(
                "Relatorio gerado",
                summary_text + "\n\nErros: " + str(error_count),
            )
        else:
            messagebox.showinfo("Relatorio gerado", summary_text)


def run_app() -> None:
    if tk is None or ttk is None or filedialog is None or messagebox is None:
        raise RuntimeError("Tkinter não está disponível neste ambiente.")

    root = tk.Tk()
    AnalisadorApp(root)
    root.mainloop()
