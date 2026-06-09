from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from organizer.folders import build_analysis_summary, organize_single, write_report
from parser.filename import (
    Action,
    build_output_filename,
    parse_input_filename,
    resolve_placa_for_action,
    validate_placa,
)
from review.session import ReviewSession


class AnalisadorApp:
    ZOOM_MIN = 0.5
    ZOOM_MAX = 4.0
    ZOOM_STEP = 1.1

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Analisador de Placas")
        self.root.geometry("1200x760")
        self.root.minsize(960, 640)

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

        self._build_ui()
        self._refresh_view()

    def _build_ui(self) -> None:
        setup_frame = ttk.LabelFrame(self.root, text="Configuracao inicial", padding=8)
        setup_frame.pack(fill=tk.X, padx=8, pady=(8, 0))

        source_row = ttk.Frame(setup_frame)
        source_row.pack(fill=tk.X, pady=2)
        ttk.Label(source_row, text="Pasta de origem:", width=16).pack(side=tk.LEFT)
        self.source_folder_label = ttk.Label(
            source_row,
            text="Nao selecionada",
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
        ttk.Label(output_row, text="Pasta de saida:", width=16).pack(side=tk.LEFT)
        self.output_folder_label = ttk.Label(
            output_row,
            text="Nao selecionada",
            foreground="#555",
        )
        self.output_folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            output_row,
            text="Escolher saida",
            command=self._choose_output_folder,
        ).pack(side=tk.RIGHT)

        action_row = ttk.Frame(setup_frame)
        action_row.pack(fill=tk.X, pady=(8, 0))
        self.start_button = ttk.Button(
            action_row,
            text="Iniciar analise",
            command=self._start_analysis,
            state=tk.DISABLED,
        )
        self.start_button.pack(side=tk.LEFT)
        ttk.Label(
            action_row,
            text="Escolha origem e saida antes de revisar as imagens.",
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
            text="Gerar relatorio",
            command=self._finish_batch,
            state=tk.DISABLED,
        )
        self.finish_button.pack(side=tk.RIGHT)

        content = ttk.Frame(self.root, padding=8)
        content.pack(fill=tk.BOTH, expand=True)
        self.content_frame = content

        self.image_frame = ttk.LabelFrame(content, text="Imagem", padding=8)
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.image_canvas = tk.Canvas(
            self.image_frame,
            highlightthickness=0,
            bg="#1e1e1e",
        )
        self.image_canvas.pack(fill=tk.BOTH, expand=True)
        self.image_canvas.bind("<MouseWheel>", self._on_image_wheel)
        self.image_canvas.bind("<ButtonPress-1>", self._on_image_drag_start)
        self.image_canvas.bind("<B1-Motion>", self._on_image_drag_move)
        self.image_canvas.bind("<ButtonRelease-1>", self._on_image_drag_end)
        self.image_frame.bind("<Configure>", self._on_image_frame_resize)

        side = ttk.Frame(content, padding=(8, 0, 0, 0), width=320)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)

        actions_frame = ttk.LabelFrame(side, text="Acoes", padding=8)
        actions_frame.pack(fill=tk.X, side=tk.TOP)

        self.certa_button = ttk.Button(
            actions_frame,
            text="Certo",
            command=self._apply_certo,
        )
        self.certa_button.pack(fill=tk.X, pady=2)

        self.errada_button = ttk.Button(
            actions_frame,
            text="Falha tecnica",
            command=lambda: self._apply_action(Action.ERRADA),
        )
        self.errada_button.pack(fill=tk.X, pady=2)

        self.obstrucao_button = ttk.Button(
            actions_frame,
            text="Obstrucao - 000000",
            command=lambda: self._apply_action(Action.OBSTRUCAO),
        )
        self.obstrucao_button.pack(fill=tk.X, pady=2)

        manual_frame = ttk.LabelFrame(
            actions_frame,
            text="Placa correta (opcional)",
            padding=6,
        )
        manual_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(
            manual_frame,
            text="Preencha se corrigiu a placa. Vazio = ja veio certa.",
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
            text="Proxima",
            command=self._go_next,
            state=tk.DISABLED,
        )
        self.next_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.skip_button = ttk.Button(
            side,
            text="Pular arquivo invalido",
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
            ("periodo", "Periodo"),
            ("horario", "Horario"),
            ("placa", "Placa detectada"),
            ("nome_saida", "Nome de saida"),
            ("decisao", "Decisao atual"),
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
            title="Selecionar pasta de saida",
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
                "Configuracao incompleta",
                "Selecione a pasta de origem e a pasta de saida.",
            )
            return

        total, invalid = self.session.load_folder(
            self._source_folder,
            self._output_folder,
        )
        if total == 0:
            messagebox.showinfo(
                "Pasta vazia",
                "Nenhuma imagem JPG encontrada na pasta de origem ou subpastas.",
            )
            return

        self._analysis_started = True
        self.start_button.config(state=tk.DISABLED)
        self._set_review_enabled(True)

        if invalid:
            messagebox.showwarning(
                "Arquivos invalidos",
                f"{invalid} arquivo(s) com nome invalido podem ser pulados.",
            )

        self._clear_manual_entry()
        self._refresh_view()

    def _clear_manual_entry(self) -> None:
        self.manual_entry.delete(0, tk.END)

    def _set_review_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for widget in (
            self.certa_button,
            self.errada_button,
            self.obstrucao_button,
            self.manual_entry,
            self.prev_button,
            self.next_button,
            self.skip_button,
        ):
            widget.config(state=state)
        if not enabled:
            self.finish_button.config(state=tk.DISABLED)
        else:
            self.finish_button.config(state=tk.NORMAL)

    def _refresh_view(self) -> None:
        current = self.session.current
        total = self.session.total
        decided = self.session.decided_count

        self.progress_label.config(text=f"{decided} / {total}")
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
                    text="Configure origem e saida, depois clique em Iniciar analise."
                )
            else:
                self.warning_label.config(text="")
            self._set_action_state(tk.DISABLED)
            return

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
            if current.placa_final:
                decisao += f" -> {current.placa_final}"

        self.meta_labels["arquivo"].config(text=current.filepath.name)
        self.meta_labels["equipamento"].config(text=parsed.n_serie or "-")
        self.meta_labels["faixa"].config(text=parsed.faixa or "-")
        self.meta_labels["sentido"].config(text=parsed.sentido or "-")
        self.meta_labels["periodo"].config(text=periodo_label)
        self.meta_labels["horario"].config(text=parsed.horario or "-")
        self.meta_labels["placa"].config(text=parsed.placa_detectada or "-")
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

    def _current_output_name(self, current) -> str | None:
        if current.placa_final:
            return build_output_filename(current.parsed, current.placa_final)

        if current.parsed.valid:
            placa = self._preview_placa_for_certo(current)
            if placa:
                return build_output_filename(current.parsed, placa)
        return None

    def _update_output_preview(self, _event=None) -> None:
        current = self.session.current
        if current is None or not current.parsed.valid:
            return
        preview = self._current_output_name(current)
        self.meta_labels["nome_saida"].config(text=preview or "-")

    def _set_action_state(self, state: str) -> None:
        if not self._analysis_started:
            state = tk.DISABLED
        self.certa_button.config(state=state)
        self.errada_button.config(state=state)
        self.obstrucao_button.config(state=state)
        self.manual_entry.config(state=state)

    def _clear_image(self) -> None:
        self._current_pil_image = None
        self._photo = None
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_data = None
        self.image_canvas.delete("all")
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        self.zoom_label.config(text=f"{int(self._zoom_level * 100)}%")

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

        placa_final, error = resolve_placa_for_action(current.parsed, action)
        if error or placa_final is None:
            messagebox.showerror("Erro", error or "Nao foi possivel aplicar a acao.")
            return

        self._finalize_decision(action, placa_final)

    def _finalize_decision(self, action: Action, placa_final: str) -> None:
        self.session.set_decision(action, placa_final)
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
            messagebox.showerror(
                "Erro ao copiar",
                error or "Nao foi possivel copiar a imagem.",
            )
            self.session.process_errors.append(
                f"{current.parsed.source_name}: {error}"
            )
            return

        entry = (current.parsed.source_name, str(target))
        if entry not in self.session.processed_paths:
            self.session.processed_paths.append(entry)

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
    root = tk.Tk()
    AnalisadorApp(root)
    root.mainloop()
