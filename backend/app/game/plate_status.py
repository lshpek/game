"""Structured, qualified collector associations for plate series."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.game.plate_rarity import Rarity, rarity_rank
from app.game.plate_traits import PLATE_TRAITS, trait_labels


@dataclass(frozen=True, slots=True)
class StatusSeries:
    code: str
    latin_code: str
    category: str
    association_en: str
    association_ru: str
    collector_multiplier: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


RUSSIAN_STATUS_SERIES: dict[str, StatusSeries] = {
    "АМР": StatusSeries(
        "АМР", "AMR", "PUBLIC_ASSOCIATION",
        "A publicly discussed status-series association; this does not verify official use or ownership.",
        "Публично обсуждаемая статусная ассоциация серии; это не подтверждает официальное использование или владение.",
        1.75,
    ),
    "ЕКХ": StatusSeries(
        "ЕКХ", "EKH", "PUBLIC_ASSOCIATION",
        "A publicly discussed status-series association; this does not verify official use or ownership.",
        "Публично обсуждаемая статусная ассоциация серии; это не подтверждает официальное использование или владение.",
        1.75,
    ),
    "ММР": StatusSeries("ММР", "MMR", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "КОО": StatusSeries("КОО", "KOO", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "АОО": StatusSeries("АОО", "AOO", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "ММС": StatusSeries("ММС", "MMS", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "РМР": StatusSeries("РМР", "RMR", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "ВОР": StatusSeries("ВОР", "VOR", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "МУР": StatusSeries("МУР", "MUR", "COLLECTOR_ASSOCIATION", "A series discussed by collectors; no provenance or ownership is implied.", "Серия, обсуждаемая коллекционерами; происхождение и владение не подразумеваются.", 1.55),
    "ААА": StatusSeries("ААА", "AAA", "AESTHETIC_ONLY", "Repeated letters are valued for visual symmetry only; no status association is asserted.", "Повтор букв ценится только за визуальную симметрию; статусная ассоциация не заявляется.", 1.4),
    "ООО": StatusSeries("ООО", "OOO", "AESTHETIC_ONLY", "Repeated letters are valued for visual symmetry only; no status association is asserted.", "Повтор букв ценится только за визуальную симметрию; статусная ассоциация не заявляется.", 1.4),
    "МММ": StatusSeries("МММ", "MMM", "AESTHETIC_ONLY", "Repeated letters are valued for visual symmetry only; no status association is asserted.", "Повтор букв ценится только за визуальную симметрию; статусная ассоциация не заявляется.", 1.4),
}


def status_series_for(country_code: str, letter_groups: list[str]) -> StatusSeries | None:
    """Resolve a known series from a country's generated letter groups."""
    if str(country_code).upper() != "RUS":
        return None
    return RUSSIAN_STATUS_SERIES.get("".join(letter_groups).upper())


def collector_bio(
    *,
    rarity: str,
    kind: str,
    country_code: str,
    letter_groups: list[str],
    traits: list[str],
    region_code: str | None = None,
    region_name_en: str = "",
    region_name_ru: str = "",
) -> dict[str, object] | None:
    """Build factual, structured explanation only for Epic-or-higher collectibles."""
    if rarity_rank(rarity) < rarity_rank(Rarity.EPIC):
        return None

    series = status_series_for(country_code, letter_groups)
    patterns = [code for code in traits if code in PLATE_TRAITS][:3]
    reason_codes = ["rarity"]
    if series is not None:
        reason_codes.insert(0, "status_series")
    if patterns:
        reason_codes.append("pattern")
    if region_code:
        reason_codes.append("region")

    return {
        "kind": kind,
        "status_category": series.category if series else None,
        "series_code": series.code if series else None,
        "series_latin_code": series.latin_code if series else None,
        "association_en": series.association_en if series else "This is a procedurally generated collectible; no real vehicle or owner is represented.",
        "association_ru": series.association_ru if series else "Это процедурный коллекционный объект; реальный автомобиль или владелец не представлен.",
        "region_code": region_code,
        "region_name_en": region_name_en,
        "region_name_ru": region_name_ru,
        "pattern_codes": patterns,
        "pattern_labels_en": trait_labels(patterns, "en"),
        "pattern_labels_ru": trait_labels(patterns, "ru"),
        "reason_codes": reason_codes,
    }


__all__ = ["RUSSIAN_STATUS_SERIES", "StatusSeries", "collector_bio", "status_series_for"]
