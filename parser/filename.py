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
    "metadata_after_horario_length": 15,
}

SENTIDO_PATTERN = re.compile(r"(Leste|Oeste|Norte|Sul)", re.IGNORECASE)
PLACA_PATTERN = re.compile(r"^[A-Z0-9]{6,7}$")
PLACA_PREFIX_PATTERN = re.compile(r"^[A-Z]{3}[0-9]")
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
    id_final: int = 0


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


def extract_placa(stem: str, sentido_end: int) -> str:
    start = (
        sentido_end
        + SLICES["horario_offset_after_sentido"]
        + SLICES["horario_length"]
        + SLICES["metadata_after_horario_length"]
    )
    end = start + PLACA_LENGTH
    if end > len(stem):
        return ""

    plate = stem[start:end]
    if not plate:
        return ""

    if set(plate) == {"0"}:
        return OBSTRUCAO_PLACA

    if PLACA_PREFIX_PATTERN.match(plate):
        return plate

    if PLACA_PATTERN.match(plate):
        return plate

    return ""


def extract_sentido(stem: str) -> str:
    match = SENTIDO_PATTERN.search(stem)
    if match:
        return match.group(1).capitalize()
    return "DESCONHECIDO"


def format_horario_display(horario: str) -> str:
    if len(horario) == 6 and horario.isdigit():
        return f"{horario[:2]}:{horario[2:4]}:{horario[4:6]}"
    return horario


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
    placa = extract_placa(stem, sentido_match.end()).upper()
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
    if action in (Action.CERTA, Action.ERRADA):
        if manual_placa and manual_placa.strip():
            ok, result = validate_placa(manual_placa)
            if not ok:
                return None, result
            return result, None
        placa = parsed.placa_detectada.upper()
        if not placa:
            return None, "Placa detectada vazia."
        return placa, None

    if action == Action.OBSTRUCAO:
        return OBSTRUCAO_PLACA, None

    return None, "Acao invalida."


def build_output_filename(
    parsed: ParsedImage,
    placa_final: str,
    id_final: int | None = None,
) -> str:
    classificacao = parsed.id_final if id_final is None else id_final
    parts = [
        parsed.n_serie,
        parsed.faixa,
        parsed.sentido.upper(),
        parsed.periodo,
        parsed.horario,
        placa_final.upper(),
        str(classificacao),
    ]
    return "_".join(parts) + ".jpg"


def is_placa_corrected(
    parsed: ParsedImage, action: Action, placa_final: str | None
) -> bool:
    if action != Action.CERTA or not placa_final:
        return False
    return placa_final.upper() != parsed.placa_detectada.upper()


def resolve_destination(
    action: Action,
    *,
    corrected: bool = False,
    veiculo_especial: bool = False,
) -> list[str]:
    if action == Action.OBSTRUCAO:
        return ["obstruida"]
    if action == Action.ERRADA:
        parts = ["falha_tecnica"]
    elif corrected:
        parts = ["certo", "imagens_corrigidas"]
    else:
        parts = ["certo"]
    if veiculo_especial:
        parts.append("veiculos_especiais")
    return parts
