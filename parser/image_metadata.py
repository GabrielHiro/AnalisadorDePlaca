from __future__ import annotations

import re
from pathlib import Path

from parser.filename import (
    OBSTRUCAO_PLACA,
    PLACA_PATTERN,
    ParsedImage,
    derive_periodo,
    parse_input_filename,
)

METADATA_TAIL_BYTES = 100_000
METROLOGICO_MARKER = "[Metrologico]"
NMETROLOGICO_MARKER = "[NMetrologico]"
CARDINAL_SENTIDOS = ("Leste", "Oeste", "Norte", "Sul")
CLASSIFICACAO_BY_ID = {
    0: "não avaliada",
    4: "caminhão / onibus",
    5: "motocicleta",
    6: "automovel",
    7: "caminhao",
    8: "onibus",
    255: "indefinido",
}
HORA_PATTERN = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


def format_classificacao(id_final: int) -> str:
    meaning = CLASSIFICACAO_BY_ID.get(id_final, CLASSIFICACAO_BY_ID[0])
    return f"{id_final} ({meaning})"


def classificacao_option_label(id_final: int) -> str:
    meaning = CLASSIFICACAO_BY_ID.get(id_final, CLASSIFICACAO_BY_ID[0])
    return f"{id_final} - {meaning}"


def _read_metadata_text(filepath: Path) -> str:
    with filepath.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - METADATA_TAIL_BYTES))
        return handle.read().decode("latin-1", errors="replace")


def _parse_ini_section(text: str, marker: str) -> dict[str, str]:
    start = text.find(marker)
    if start < 0:
        return {}

    rest = text[start + len(marker) :]
    end = rest.find("\n[")
    block = rest[:end] if end >= 0 else rest

    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        fields[key.strip()] = value.strip()
    return fields


def _format_n_serie(raw: str) -> str:
    digits = raw.strip()
    if not digits.isdigit():
        return digits
    return digits.zfill(7)[-7:]


def _format_horario_from_hora(hora: str) -> str:
    hora = hora.strip()
    match = HORA_PATTERN.match(hora)
    if not match:
        digits = re.sub(r"\D", "", hora)
        return digits[:6] if len(digits) >= 6 else ""
    hour, minute, second = match.groups()
    return f"{int(hour):02d}{minute}{second}"


def _normalize_placa(raw: str) -> str:
    placa = raw.strip().upper()
    if not placa:
        return OBSTRUCAO_PLACA
    if set(placa) == {"0"}:
        return OBSTRUCAO_PLACA
    if PLACA_PATTERN.match(placa):
        return placa
    return ""


def _normalize_sentido_label(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    value = value.replace("/", "-").replace("\\", "-")
    value = re.sub(r"\s+", "-", value)
    return re.sub(r"-{2,}", "-", value)


def _match_cardinal(value: str) -> str | None:
    for name in CARDINAL_SENTIDOS:
        if value.lower() == name.lower():
            return name
    return None


def _resolve_sentido(direcao: str, sentido_fallback: str) -> str:
    for candidate in (direcao, sentido_fallback):
        value = _normalize_sentido_label(candidate)
        if not value or value.isdigit():
            continue
        return _match_cardinal(value) or value
    return "DESCONHECIDO"


def _extract_placa(nmetrologico: dict[str, str]) -> str:
    for key in ("Placa", "PlacaNaoDatacheck"):
        raw = nmetrologico.get(key, "").strip()
        if raw:
            return raw
    return ""


def _lookup_field(sections: list[dict[str, str]], *names: str) -> str:
    wanted = {name.upper() for name in names}
    for section in sections:
        for key, value in section.items():
            if key.strip().upper() in wanted:
                return value.strip()
    return ""


def _parse_id_final(*sections: dict[str, str]) -> int:
    raw = _lookup_field(list(sections), "ID_FINAL")
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    if value not in CLASSIFICACAO_BY_ID:
        return 0
    return value


def parse_from_image_metadata(filepath: Path) -> ParsedImage | None:
    try:
        text = _read_metadata_text(filepath)
    except OSError:
        return None

    nmetrologico = _parse_ini_section(text, NMETROLOGICO_MARKER)
    metrologico = _parse_ini_section(text, METROLOGICO_MARKER)

    if not nmetrologico and not metrologico:
        return None

    n_serie = _format_n_serie(
        nmetrologico.get("NSerie") or metrologico.get("NSerie", "")
    )
    faixa = (nmetrologico.get("Faixa") or metrologico.get("Faixa", "")).strip()
    horario = _format_horario_from_hora(
        nmetrologico.get("Hora") or metrologico.get("Hora", "")
    )
    sentido = _resolve_sentido(
        nmetrologico.get("Direcao", ""),
        metrologico.get("Sentido", ""),
    )
    placa = _normalize_placa(_extract_placa(nmetrologico))
    id_final = _parse_id_final(nmetrologico, metrologico)

    if not n_serie or not faixa or not horario or not placa:
        return ParsedImage(
            source_name=filepath.name,
            n_serie=n_serie,
            faixa=faixa,
            sentido=sentido,
            periodo="N",
            horario=horario,
            placa_detectada=placa,
            periodo_folder="noturno",
            valid=False,
            error="Metadados da imagem incompletos (NMetrologico/Metrologico).",
            id_final=id_final,
        )

    if sentido == "DESCONHECIDO":
        return ParsedImage(
            source_name=filepath.name,
            n_serie=n_serie,
            faixa=faixa,
            sentido=sentido,
            periodo="N",
            horario=horario,
            placa_detectada=placa,
            periodo_folder="noturno",
            valid=False,
            error="Direcao/sentido nao encontrado nos metadados da imagem.",
            id_final=id_final,
        )

    periodo, periodo_folder = derive_periodo(horario)
    return ParsedImage(
        source_name=filepath.name,
        n_serie=n_serie,
        faixa=faixa,
        sentido=sentido,
        periodo=periodo,
        horario=horario,
        placa_detectada=placa,
        periodo_folder=periodo_folder,
        valid=True,
        id_final=id_final,
    )


def parse_input_image(filepath: Path) -> ParsedImage:
    parsed_filename = parse_input_filename(filepath.name)
    if parsed_filename.valid:
        return parsed_filename

    parsed_metadata = parse_from_image_metadata(filepath)
    if parsed_metadata is not None:
        return parsed_metadata

    return parsed_filename
