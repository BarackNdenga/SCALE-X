"""SCALE-X Data Fitness Engine — analyse légère sans base de données.

Le moteur est volontairement autonome pour la V0.1 : il accepte des fichiers
CSV, JSON, JSONL et TXT, travaille en mémoire, puis renvoie un rapport JSON.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000

MISSING_MARKERS = {"", "na", "n/a", "null", "none", "nan", "-", "unknown"}
PLACEHOLDER_PATTERN = re.compile(r"\b(test|testing|lorem|ipsum|changeme|todo|tbd|dummy|sample|foobar)\b", re.I)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.I)
SECRET_PATTERN = re.compile(r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*[^\s,;]+", re.I)
WORD_PATTERN = re.compile(r"[\wÀ-ÿ'-]+", re.UNICODE)

LANGUAGE_MARKERS = {
    "français": {"le", "la", "les", "des", "une", "dans", "pour", "avec", "est", "que", "sur", "pas", "et"},
    "anglais": {"the", "and", "for", "with", "this", "that", "is", "are", "from", "not", "of", "to"},
}


@dataclass
class ParsedDataset:
    rows: list[dict[str, Any]]
    columns: list[str]
    format: str
    warnings: list[str] = field(default_factory=list)
    parse_errors: int = 0


def _decode(data: bytes) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        return data.decode("utf-8-sig"), warnings
    except UnicodeDecodeError:
        warnings.append("Le fichier n'est pas entièrement en UTF-8 ; les caractères invalides ont été remplacés.")
        return data.decode("utf-8", errors="replace"), warnings


def _normalise_row(row: dict[Any, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        column = str(key).strip() or "column"
        if isinstance(value, (dict, list)):
            result[column] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            result[column] = ""
        elif isinstance(value, bool):
            result[column] = "true" if value else "false"
        else:
            result[column] = value
    return result


def _rows_from_json(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            return [{"value": item} for item in payload]
        return [_normalise_row(item) for item in payload]
    if isinstance(payload, dict):
        for key in ("data", "rows", "items", "records", "results"):
            if isinstance(payload.get(key), list):
                return _rows_from_json(payload[key])
        return [_normalise_row(payload)]
    return [{"value": payload}]


def _parse_csv(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        warnings.append("Le séparateur CSV n'a pas pu être détecté ; la virgule a été utilisée.")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("Le CSV ne contient pas de ligne d'en-tête exploitable.")
    rows: list[dict[str, Any]] = []
    for row in reader:
        if None in row:
            warnings.append("Certaines lignes contiennent plus de champs que l'en-tête.")
            row.pop(None, None)
        rows.append(_normalise_row(row))
    return rows, warnings


def parse_dataset(filename: str, data: bytes) -> ParsedDataset:
    if not data:
        raise ValueError("Le fichier est vide.")
    if len(data) > MAX_BYTES:
        raise ValueError(f"Le fichier dépasse la limite de {MAX_BYTES // (1024 * 1024)} MB.")

    text, warnings = _decode(data)
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    stripped = text.lstrip()

    if extension in {"jsonl", "ndjson"}:
        rows: list[dict[str, Any]] = []
        errors = 0
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                rows.extend(_rows_from_json(value))
            except json.JSONDecodeError:
                errors += 1
                if errors <= 5:
                    warnings.append(f"Ligne JSONL invalide ignorée : {line_number}.")
        parsed_format = "JSONL"
    elif extension == "json" or (not extension and stripped[:1] in "[{" ):
        try:
            rows = _rows_from_json(json.loads(text))
            errors = 0
            parsed_format = "JSON"
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalide : {exc.msg}.") from exc
    elif extension == "txt":
        rows = [{"text": line} for line in text.splitlines() if line.strip()]
        errors = 0
        parsed_format = "TXT"
    else:
        rows, csv_warnings = _parse_csv(text)
        warnings.extend(csv_warnings)
        errors = 0
        parsed_format = "CSV"

    if len(rows) > MAX_ROWS:
        warnings.append(f"Le fichier contenait plus de {MAX_ROWS} lignes ; seules les {MAX_ROWS} premières ont été analysées.")
        rows = rows[:MAX_ROWS]
    if not rows:
        raise ValueError("Aucune ligne exploitable n'a été trouvée dans le fichier.")

    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)
    for row in rows:
        for column in columns:
            row.setdefault(column, "")
    return ParsedDataset(rows, columns, parsed_format, warnings, errors)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    normalised = str(value).strip().lower()
    return normalised in MISSING_MARKERS


def _as_number(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        number = float(str(value).strip().replace(",", "."))
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _infer_type(values: list[Any]) -> tuple[str, float]:
    present = [value for value in values if not _is_missing(value)]
    if not present:
        return "empty", 0.0
    numeric = sum(_as_number(value) is not None for value in present)
    if numeric / len(present) >= 0.95:
        return "numeric", numeric / len(present)
    boolean = sum(str(value).strip().lower() in {"true", "false", "yes", "no", "oui", "non", "0", "1"} for value in present)
    if boolean / len(present) >= 0.95:
        return "boolean", boolean / len(present)
    date_like = 0
    for value in present:
        raw = str(value).strip()
        try:
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
            date_like += 1
        except ValueError:
            pass
    if date_like / len(present) >= 0.8:
        return "date", date_like / len(present)
    return "text", 1.0


def _row_signature(row: dict[str, Any], columns: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(column, "")).strip().lower() for column in columns)


def _numeric_outliers(values: list[float]) -> tuple[int, float | None, float | None]:
    if len(values) < 4:
        return 0, None, None
    ordered = sorted(values)
    q1 = statistics.quantiles(ordered, n=4, method="inclusive")[0]
    q3 = statistics.quantiles(ordered, n=4, method="inclusive")[2]
    iqr = q3 - q1
    if iqr == 0:
        return 0, q1, q3
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return sum(value < lower or value > upper for value in values), lower, upper


def _language_stats(rows: list[dict[str, Any]], columns: list[str], types: dict[str, str]) -> dict[str, Any]:
    text_columns = [column for column in columns if types[column] == "text"]
    tokens: list[str] = []
    characters = 0
    non_empty_values = 0
    for row in rows:
        for column in text_columns:
            value = str(row.get(column, "")).strip()
            if not value:
                continue
            non_empty_values += 1
            characters += len(value)
            tokens.extend(token.lower() for token in WORD_PATTERN.findall(value))
    language_scores = {language: sum(token in markers for token in tokens) for language, markers in LANGUAGE_MARKERS.items()}
    language = "indéterminée"
    if tokens and max(language_scores.values(), default=0) > 0:
        language = max(language_scores, key=language_scores.get)
    return {
        "text_columns": text_columns,
        "language_estimate": language,
        "word_count": len(tokens),
        "unique_word_ratio": round(len(set(tokens)) / len(tokens) * 100, 1) if tokens else None,
        "average_words_per_value": round(len(tokens) / non_empty_values, 1) if non_empty_values else 0,
        "average_characters_per_value": round(characters / non_empty_values, 1) if non_empty_values else 0,
        "top_words": [{"word": word, "count": count} for word, count in Counter(tokens).most_common(10)],
    }


def analyse_dataset(parsed: ParsedDataset) -> dict[str, Any]:
    rows, columns = parsed.rows, parsed.columns
    row_count, column_count = len(rows), len(columns)
    total_cells = max(row_count * column_count, 1)
    missing_cells = sum(_is_missing(row.get(column)) for row in rows for column in columns)
    empty_rows = sum(all(_is_missing(row.get(column)) for column in columns) for row in rows)
    complete_rows = sum(all(not _is_missing(row.get(column)) for column in columns) for row in rows)

    duplicate_counter = Counter(_row_signature(row, columns) for row in rows)
    duplicate_rows = sum(count - 1 for count in duplicate_counter.values() if count > 1)
    duplicate_groups = sum(1 for count in duplicate_counter.values() if count > 1)

    column_reports: list[dict[str, Any]] = []
    types: dict[str, str] = {}
    suspicious_samples: list[dict[str, Any]] = []
    suspicious_total = 0
    numeric_outlier_total = 0
    for column in columns:
        values = [row.get(column, "") for row in rows]
        inferred_type, consistency = _infer_type(values)
        types[column] = inferred_type
        present = [value for value in values if not _is_missing(value)]
        unique_count = len({str(value).strip().lower() for value in present})
        report: dict[str, Any] = {
            "name": column,
            "type": inferred_type,
            "type_consistency": round(consistency * 100, 1),
            "missing": sum(_is_missing(value) for value in values),
            "missing_ratio": round(sum(_is_missing(value) for value in values) / row_count * 100, 1),
            "unique_values": unique_count,
            "unique_ratio": round(unique_count / len(present) * 100, 1) if present else 0,
        }
        if inferred_type == "numeric":
            numbers = [number for number in (_as_number(value) for value in values) if number is not None]
            outliers, lower, upper = _numeric_outliers(numbers)
            numeric_outlier_total += outliers
            report.update({
                "min": min(numbers) if numbers else None,
                "max": max(numbers) if numbers else None,
                "mean": round(statistics.mean(numbers), 4) if numbers else None,
                "median": round(statistics.median(numbers), 4) if numbers else None,
                "outliers": outliers,
                "outlier_bounds": {"lower": lower, "upper": upper} if lower is not None else None,
            })
        else:
            report["top_values"] = [{"value": str(value), "count": count} for value, count in Counter(str(value) for value in present).most_common(5)]
        column_reports.append(report)

        for row_index, value in enumerate(values, 1):
            raw = str(value)
            reason: str | None = None
            if "\x00" in raw or any(ord(char) < 9 for char in raw):
                reason = "caractère de contrôle"
            elif SECRET_PATTERN.search(raw):
                reason = "motif de secret ou de token"
            elif PLACEHOLDER_PATTERN.search(raw):
                reason = "valeur de test ou placeholder"
            elif EMAIL_PATTERN.search(raw) and any(word in column.lower() for word in ("email", "mail", "contact")):
                reason = "donnée personnelle potentielle : e-mail"
            elif URL_PATTERN.search(raw) and any(word in column.lower() for word in ("url", "link", "website", "site")):
                reason = "URL à vérifier"
            if reason:
                suspicious_total += 1
                if len(suspicious_samples) < 50:
                    suspicious_samples.append({"row": row_index, "column": column, "reason": reason})

    categorical_candidates = []
    for column in columns:
        report = next(item for item in column_reports if item["name"] == column)
        if types[column] in {"text", "boolean"} and 1 < report["unique_values"] <= min(20, max(2, row_count // 2)):
            categorical_candidates.append(column)
    label_priority = sorted(categorical_candidates, key=lambda name: (not any(word in name.lower() for word in ("label", "class", "target", "category", "type")), name))
    class_column = label_priority[0] if label_priority else None
    class_distribution = None
    rare_cases_score: float | None = None
    if class_column:
        counts = Counter(str(row.get(class_column, "")).strip() or "[missing]" for row in rows)
        total = sum(counts.values())
        distribution = [{"label": label, "count": count, "share": round(count / total * 100, 1)} for label, count in counts.most_common()]
        shares = [item["share"] for item in distribution]
        rare_cases_score = min(100.0, (min(shares) / max(shares)) * 100) if len(shares) > 1 else 100.0
        class_distribution = {"column": class_column, "classes": distribution, "class_count": len(distribution)}

    if rare_cases_score is None:
        numeric_observations = sum(
            1 for report in column_reports if report["type"] == "numeric"
            for row in rows if not _is_missing(row.get(report["name"]))
        )
        if numeric_observations:
            rare_cases_score = max(0.0, 100 - numeric_outlier_total / numeric_observations * 100)

    missing_ratio = missing_cells / total_cells
    duplicate_ratio = duplicate_rows / max(row_count, 1)
    quality_score = max(0.0, 100 - missing_ratio * 80 - duplicate_ratio * 20)
    coverage_score = complete_rows / max(row_count, 1) * 100
    diversity_score = statistics.mean(item["unique_ratio"] for item in column_reports) if column_reports else 0
    consistency_score = statistics.mean(item["type_consistency"] for item in column_reports) if column_reports else 0
    suspicious_ratio = suspicious_total / total_cells
    integrity_score = max(0.0, 100 - suspicious_ratio * 300 - (parsed.parse_errors / max(row_count, 1)) * 100)
    component_scores: dict[str, float | None] = {
        "quality": round(quality_score, 1),
        "coverage": round(coverage_score, 1),
        "diversity": round(diversity_score, 1),
        "rare_cases": round(rare_cases_score, 1) if rare_cases_score is not None else None,
        "consistency": round(consistency_score, 1),
        "integrity": round(integrity_score, 1),
    }
    component_weights = {"quality": 0.25, "coverage": 0.15, "diversity": 0.15, "rare_cases": 0.15, "consistency": 0.15, "integrity": 0.15}
    available = [(name, score, component_weights[name]) for name, score in component_scores.items() if score is not None]
    total_weight = sum(weight for _, _, weight in available)
    dfs = round(sum(score * weight for _, score, weight in available) / total_weight, 1) if total_weight else 0.0

    return {
        "engine": "SCALE-X Data Fitness Engine",
        "engine_version": "0.1.0",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "dataset": {
            "format": parsed.format,
            "rows": row_count,
            "columns": column_count,
            "cells": row_count * column_count,
            "column_names": columns,
            "warnings": parsed.warnings,
            "parse_errors": parsed.parse_errors,
        },
        "dfs": {
            "score": dfs,
            "label": "EXCELLENT" if dfs >= 85 else "GOOD" if dfs >= 70 else "TO REVIEW" if dfs >= 50 else "CRITICAL",
            "components": component_scores,
            "weights": component_weights,
            "unavailable_components": [name for name, score in component_scores.items() if score is None],
        },
        "quality": {
            "missing_cells": missing_cells,
            "missing_ratio": round(missing_ratio * 100, 1),
            "empty_rows": empty_rows,
            "complete_rows": complete_rows,
            "duplicate_rows": duplicate_rows,
            "duplicate_groups": duplicate_groups,
            "duplicate_ratio": round(duplicate_ratio * 100, 1),
            "outlier_values": numeric_outlier_total,
        },
        "diversity": {
            "average_unique_ratio": round(diversity_score, 1),
            "columns": [{"name": item["name"], "unique_values": item["unique_values"], "unique_ratio": item["unique_ratio"]} for item in column_reports],
        },
        "bias": {
            "status": "analysed" if class_distribution else "not_enough_categorical_signal",
            "class_distribution": class_distribution,
            "imbalance_note": "La distribution est indicative ; elle ne remplace pas une analyse métier du label cible." if class_distribution else "Aucune colonne catégorielle candidate n'a été identifiée.",
        },
        "rare_cases": {
            "score": round(rare_cases_score, 1) if rare_cases_score is not None else None,
            "outlier_values": numeric_outlier_total,
            "method": "Équilibre des classes si une colonne catégorielle candidate existe ; sinon taux réel de valeurs numériques hors bornes IQR.",
        },
        "consistency": {
            "score": round(consistency_score, 1),
            "columns": column_reports,
        },
        "integrity": {
            "score": round(integrity_score, 1),
            "suspicious_count": suspicious_total,
            "suspicious_samples": suspicious_samples,
            "privacy_note": "Les données brutes ne sont pas conservées par le moteur ; ce rapport contient seulement des statistiques et des exemples de motifs détectés.",
        },
        "linguistics": _language_stats(rows, columns, types),
        "summary": {
            "headline": "Voici la santé de votre dataset.",
            "recommendations": _recommendations(missing_ratio, duplicate_ratio, numeric_outlier_total, suspicious_total, class_distribution, parsed.warnings),
        },
        "provenance": {
            "source": "uploaded_file",
            "simulated": False,
            "raw_data_retained": False,
            "rows_analysed": row_count,
            "columns_analysed": column_count,
            "calculation_note": "Toutes les métriques et tous les scores sont dérivés des valeurs présentes dans le fichier importé.",
        },
    }


def _recommendations(
    missing_ratio: float,
    duplicate_ratio: float,
    outlier_count: int,
    suspicious_count: int,
    class_distribution: dict[str, Any] | None,
    warnings: list[str],
) -> list[str]:
    recommendations: list[str] = []
    if missing_ratio > 0.05:
        recommendations.append("Traiter les valeurs manquantes avant l'entraînement ou l'évaluation d'un modèle.")
    if duplicate_ratio > 0.02:
        recommendations.append("Examiner les doublons : ils peuvent surreprésenter certains exemples et fausser les scores.")
    if outlier_count:
        recommendations.append("Vérifier les valeurs extrêmes avec un expert métier avant de les supprimer.")
    if class_distribution and min(item["share"] for item in class_distribution["classes"]) < 10:
        recommendations.append("La classe la plus rare représente moins de 10 % des lignes ; prévoir une stratégie de rééquilibrage ou de pondération.")
    if suspicious_count:
        recommendations.append("Revoir les motifs suspects détectés et retirer les secrets ou données personnelles avant tout partage.")
    if warnings:
        recommendations.append("Relire les avertissements d'importation avant d'interpréter le DFS.")
    if not recommendations:
        recommendations.append("Le dataset présente une base saine pour une première exploration ; valider néanmoins les métriques avec le contexte métier.")
    return recommendations
