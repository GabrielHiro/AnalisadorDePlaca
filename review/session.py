from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from parser.filename import Action, ParsedImage
from parser.image_metadata import parse_input_image


IMAGE_EXTENSIONS = {".jpg", ".jpeg"}


def scan_image_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def build_decisions(files: list[Path]) -> tuple[list[ReviewDecision], int]:
    decisions: list[ReviewDecision] = []
    invalid_count = 0
    
    for filepath in files:
        parsed = parse_input_image(filepath)
        if not parsed.valid:
            invalid_count += 1
        decisions.append(
            ReviewDecision(
                filepath=filepath,
                parsed=parsed,
            )
        )
    
    return decisions, invalid_count


@dataclass
class ReviewDecision:
    filepath: Path
    parsed: ParsedImage
    action: Action | None = None
    placa_final: str | None = None
    skipped: bool = False
    veiculo_especial: bool = False
    classificacao: int | None = None
    output_path: Path | None = None

    @property
    def is_decided(self) -> bool:
        return self.skipped or self.action is not None


@dataclass
class ReviewSession:
    source_folder: Path | None = None
    output_folder: Path | None = None
    decisions: list[ReviewDecision] = field(default_factory=list)
    current_index: int = 0
    processed_paths: list[tuple[str, str]] = field(default_factory=list)
    process_errors: list[str] = field(default_factory=list)

    def load_folder(self, folder: Path, output_folder: Path) -> tuple[int, int]:
        self.source_folder = folder
        self.output_folder = output_folder
        self.decisions.clear()
        self.current_index = 0
        self.processed_paths.clear()
        self.process_errors.clear()

        files = scan_image_files(folder)
        self.decisions, invalid_count = build_decisions(files)

        return len(files), invalid_count

    @property
    def total(self) -> int:
        return len(self.decisions)

    @property
    def decided_count(self) -> int:
        return sum(1 for item in self.decisions if item.is_decided)

    @property
    def all_decided(self) -> bool:
        return self.total > 0 and self.decided_count == self.total

    @property
    def current(self) -> ReviewDecision | None:
        if not self.decisions or self.current_index >= len(self.decisions):
            return None
        return self.decisions[self.current_index]

    def go_next(self) -> ReviewDecision | None:
        if self.current_index < len(self.decisions) - 1:
            self.current_index += 1
        return self.current

    def go_previous(self) -> ReviewDecision | None:
        if self.current_index > 0:
            self.current_index -= 1
        return self.current

    def go_to(self, index: int) -> ReviewDecision | None:
        if 0 <= index < len(self.decisions):
            self.current_index = index
            return self.current
        return None

    def set_decision(
        self,
        action: Action,
        placa_final: str,
        *,
        veiculo_especial: bool = False,
        classificacao: int | None = None,
    ) -> None:
        item = self.current
        if item is None:
            return
        item.action = action
        item.placa_final = placa_final
        item.veiculo_especial = veiculo_especial
        item.classificacao = classificacao
        item.skipped = False

    def skip_current(self) -> None:
        item = self.current
        if item is None:
            return
        item.action = None
        item.placa_final = None
        item.veiculo_especial = False
        item.classificacao = None
        item.skipped = True

    def get_reviewable(self) -> list[ReviewDecision]:
        return [
            item
            for item in self.decisions
            if item.is_decided and item.action is not None and not item.skipped
        ]
