from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from parser.filename import (
    Action,
    build_output_filename,
    is_placa_corrected,
    resolve_destination,
)
from review.session import ReviewDecision


@dataclass
class OrganizationResult:
    copied: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    report_path: Path | None = None


@dataclass
class AnalysisSummary:
    quantidade_analisada: int
    placas_corretas: int
    falhas_tecnicas: int
    falhas_obstrucao: int


def build_target_path(
    output_root: Path,
    decision: ReviewDecision,
) -> Path:
    parsed = decision.parsed
    assert decision.action is not None
    assert decision.placa_final is not None

    corrected = is_placa_corrected(
        parsed, decision.action, decision.placa_final
    )
    veiculo_especial = (
        decision.veiculo_especial and decision.action != Action.OBSTRUCAO
    )
    category_parts = resolve_destination(
        decision.action,
        corrected=corrected,
        veiculo_especial=veiculo_especial,
    )
    classificacao = (
        decision.classificacao
        if decision.classificacao is not None
        else parsed.id_final
    )
    filename = build_output_filename(
        parsed,
        decision.placa_final,
        id_final=classificacao,
    )
    return (
        output_root
        / parsed.n_serie
        / parsed.periodo_folder
        / Path(*category_parts)
        / filename
    )


def organize_single(
    decision: ReviewDecision,
    output_root: Path,
) -> tuple[Path | None, str | None]:
    if decision.skipped or decision.action is None or decision.placa_final is None:
        return None, "Decisao incompleta."

    try:
        target = build_target_path(output_root, decision)
        if (
            decision.output_path is not None
            and decision.output_path.exists()
            and decision.output_path == target
        ):
            return decision.output_path, None

        old_path = decision.output_path
        if (
            old_path is not None
            and old_path != target
            and old_path.exists()
        ):
            old_path.unlink()

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(decision.filepath), str(target))
        decision.output_path = target
        return target, None
    except OSError as exc:
        return None, str(exc)


def build_analysis_summary(decisions: list[ReviewDecision]) -> AnalysisSummary:
    placas_corretas = 0
    falhas_tecnicas = 0
    falhas_obstrucao = 0

    for decision in decisions:
        if decision.skipped or decision.action is None:
            continue
        if decision.action == Action.CERTA:
            placas_corretas += 1
        elif decision.action == Action.ERRADA:
            falhas_tecnicas += 1
        elif decision.action == Action.OBSTRUCAO:
            falhas_obstrucao += 1

    quantidade_analisada = placas_corretas + falhas_tecnicas + falhas_obstrucao
    return AnalysisSummary(
        quantidade_analisada=quantidade_analisada,
        placas_corretas=placas_corretas,
        falhas_tecnicas=falhas_tecnicas,
        falhas_obstrucao=falhas_obstrucao,
    )


def write_report(
    summary: AnalysisSummary,
    output_root: Path,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "relatorio.csv"

    rows = [
        ("Quantidade analisada", summary.quantidade_analisada),
        ("Placas corretas", summary.placas_corretas),
        ("Falhas tecnicas", summary.falhas_tecnicas),
        ("Falhas por obstrucao", summary.falhas_obstrucao),
    ]

    with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["Indicador", "Quantidade"])
        writer.writerows(rows)

    return report_path


def organize_batch(
    decisions: list[ReviewDecision],
    output_root: Path,
) -> OrganizationResult:
    result = OrganizationResult()
    output_root.mkdir(parents=True, exist_ok=True)

    for decision in decisions:
        if decision.skipped or decision.action is None or decision.placa_final is None:
            continue

        target, error = organize_single(decision, output_root)
        if error or target is None:
            result.errors.append(f"{decision.parsed.source_name}: {error}")
            continue

        result.copied.append((decision.parsed.source_name, str(target)))

    summary = build_analysis_summary(decisions)
    result.report_path = write_report(summary, output_root)
    return result
