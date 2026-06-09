from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Action(str, Enum):
    CERTA = "certa"
    ERRADA = "errada"
    OBSTRUCAO = "obstrucao"


SLICES = {
    "nSerie": (0, 7),
    "faixa": (7, 8),
    "min_len": 64,
    "horario_offset_after_sentido": 9,
    "horario_length": 6,
}

OUTPUT_SENTIDO_LABEL = "SENTIDO"

SENTIDO_PATTERN = re.compile(r"(Leste|Oeste|Norte|Sul)", re.IGNORECASE)
PLACA_PATTERN = re.compile(r"^[A-Z0-9]{6,7}$")
PLACA_PREFIX_PATTERN = re.compile(r"^[A-Z]{3}[0-9]")
MIN_PLACA_PADDING_ZEROS = 6
PLACA_LENGTH = 7
OBSTRUCAO_PLACA = "000000"


@dataclass(frozen=True)
class ParsedImage:
    source_name: str
    n_serie: str
    faixa: str
    sentido: str
    periodo: str
    horario: str
    placa_detectada: str
    periodo_folder: str
    valid: bool
    error: str | None = None


def normalize_stem(filename: str) -> str:
    stem = Path(filename).stem
    return stem.replace(" ", "").upper()


def normalize_faixa(raw_faixa: str) -> str:
    return raw_faixa


def extract_horario(stem: str, sentido_end: int) -> str:
    start = sentido_end + SLICES["horario_offset_after_sentido"]
    end = start + SLICES["horario_length"]
    if end > len(stem):
        return ""
    return stem[start:end]


def extract_placa(stem: str) -> str:
    trailing_zeros = len(stem) - len(stem.rstrip("0"))
    if trailing_zeros < MIN_PLACA_PADDING_ZEROS:
        return ""

    candidates: list[str] = []
    standard = stem[-(trailing_zeros + PLACA_LENGTH) : -trailing_zeros]
    if len(standard) == PLACA_LENGTH:
        candidates.append(standard)

    if trailing_zeros >= 7:
        with_shared_zero = stem[-(trailing_zeros + PLACA_LENGTH - 1) : -(trailing_zeros - 1)]
        if len(with_shared_zero) == PLACA_LENGTH:
            candidates.append(with_shared_zero)

    for candidate in candidates:
        if PLACA_PREFIX_PATTERN.match(candidate):
            return candidate

    for candidate in candidates:
        if PLACA_PATTERN.match(candidate):
            return candidate

    return ""


def extract_sentido(stem: str) -> str:
    match = SENTIDO_PATTERN.search(stem)
    if match:
        return match.group(1).capitalize()
    return "DESCONHECIDO"


def derive_periodo(horario: str) -> tuple[str, str]:
    if len(horario) < 2 or not horario[:2].isdigit():
        return "N", "noturno"

    hour = int(horario[:2])
    if 6 <= hour <= 17:
        return "D", "diurno"
    return "N", "noturno"


def parse_input_filename(filename: str) -> ParsedImage:
    stem = normalize_stem(filename)
    min_len = SLICES["min_len"]

    if len(stem) < min_len:
        return ParsedImage(
            source_name=filename,
            n_serie="",
            faixa="",
            sentido="DESCONHECIDO",
            periodo="N",
            horario="",
            placa_detectada="",
            periodo_folder="noturno",
            valid=False,
            error=f"Nome muito curto ({len(stem)} chars, minimo {min_len}).",
        )

    n_serie = stem[SLICES["nSerie"][0] : SLICES["nSerie"][1]]
    faixa = normalize_faixa(stem[SLICES["faixa"][0] : SLICES["faixa"][1]])
    sentido_match = SENTIDO_PATTERN.search(stem)
    if not sentido_match:
        return ParsedImage(
            source_name=filename,
            n_serie=n_serie,
            faixa=faixa,
            sentido="DESCONHECIDO",
            periodo="N",
            horario="",
            placa_detectada="",
            periodo_folder="noturno",
            valid=False,
            error="Sentido nao encontrado no nome do arquivo.",
        )

    sentido = sentido_match.group(1).capitalize()
    horario = extract_horario(stem, sentido_match.end())
    placa = extract_placa(stem).upper()
    if not horario or not placa:
        return ParsedImage(
            source_name=filename,
            n_serie=n_serie,
            faixa=faixa,
            sentido=sentido,
            periodo="N",
            horario=horario,
            placa_detectada=placa,
            periodo_folder="noturno",
            valid=False,
            error="Horario ou placa nao encontrados no nome do arquivo.",
        )

    periodo, periodo_folder = derive_periodo(horario)

    return ParsedImage(
        source_name=filename,
        n_serie=n_serie,
        faixa=faixa,
        sentido=sentido,
        periodo=periodo,
        horario=horario,
        placa_detectada=placa,
        periodo_folder=periodo_folder,
        valid=True,
    )


def validate_placa(placa: str) -> tuple[bool, str]:
    normalized = placa.strip().upper().replace("-", "").replace(" ", "")
    if not normalized:
        return False, "Informe a placa."
    if not PLACA_PATTERN.match(normalized):
        return False, "Placa invalida. Use 6 ou 7 caracteres alfanumericos."
    return True, normalized


def resolve_placa_for_action(
    parsed: ParsedImage, action: Action, manual_placa: str | None = None
) -> tuple[str | None, str | None]:
    if action == Action.CERTA:
        if manual_placa and manual_placa.strip():
            ok, result = validate_placa(manual_placa)
            if not ok:
                return None, result
            return result, None
        placa = parsed.placa_detectada.upper()
        if not placa:
            return None, "Placa detectada vazia."
        return placa, None

    if action == Action.ERRADA:
        placa = parsed.placa_detectada.upper()
        if not placa:
            return None, "Placa detectada vazia."
        return placa, None

    if action == Action.OBSTRUCAO:
        return OBSTRUCAO_PLACA, None

    return None, "Acao invalida."


def build_output_filename(parsed: ParsedImage, placa_final: str) -> str:
    parts = [
        parsed.n_serie,
        parsed.faixa,
        OUTPUT_SENTIDO_LABEL,
        parsed.periodo,
        parsed.horario,
        placa_final.upper(),
    ]
    return "_".join(parts) + ".jpg"


def is_placa_corrected(
    parsed: ParsedImage, action: Action, placa_final: str | None
) -> bool:
    if action != Action.CERTA or not placa_final:
        return False
    return placa_final.upper() != parsed.placa_detectada.upper()


def resolve_destination(action: Action, *, corrected: bool = False) -> list[str]:
    if action == Action.OBSTRUCAO:
        return ["obstruida"]
    if action == Action.ERRADA:
        return ["falha_tecnica"]
    if corrected:
        return ["certo", "imagens_corrigidas"]
    return ["certo"]
