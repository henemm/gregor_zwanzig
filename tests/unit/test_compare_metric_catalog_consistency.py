"""
Struktureller Guard gegen wiederholtes stilles Verwerfen waehlbarer
Compare-Metriken (#1296, AC-6; gehaertet #1298, B3; umgehaengt nach #1350
Teil 3 -- Bugfix-Session 2026-07-24).

Ohne sichtbares Signal wiederholt sich der Bug-Typ von #1285/#1296/#1324 bei
der naechsten neu eingefuehrten Backend-Katalog-Metrik ein weiteres Mal.

Seit #1350 (Teil 3) ist der Backend-Katalog (`compare_metric_catalog.py`) die
einzige Quelle fuer waehlbare Compare-Metriken -- `compareMetricDefs.ts`
wurde in Commit 16c9d318 gelöscht. Ein struktureller Drift-Assert Katalog <->
Resolver (`FRONTEND_TO_RENDERER_METRIC_ID`) existiert bereits als
Modul-Import-Assert in `compare_metric_catalog.py`. UNGESCHUETZT blieb eine
dritte Kopie: die Render-Liste `CV2_METRICS` in
`src/output/renderers/email/compare_html.py` -- fehlt dort eine Zeile fuer
einen Katalog-Eintrag, ist die Metrik im Editor waehlbar, taucht aber nie in
der Mail auf (exakt der alte Bug-Typ).

Dieser Test prueft daher direkt in Python (kein TypeScript-Parsing mehr --
das brach beim Loeschen von compareMetricDefs.ts die GESAMTE Testsuite-
Collection, s. Vorfall 2026-07-24): jeder Katalog-Key hat ueber
`FRONTEND_TO_RENDERER_METRIC_ID` eine CV2_METRICS-Zeile, und umgekehrt hat
jede CV2_METRICS-Zeile (ausser "warn") einen Katalog-Ursprung.

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein patch(), kein
Datei-I/O auf Modul-Ebene. Reiner Konsistenz-Check gegen die Konstanten der
Module + echtes Logger-Verhalten (``caplog``, kein gemocktes Logging-Objekt).

SPEC: docs/specs/modules/issue_1296_compare_metrics_dropped.md
SPEC: docs/specs/modules/issue_1298_compare_metric_guard_cape_label.md
SPEC: docs/specs/modules/compare_metric_ssot_final.md
"""
from __future__ import annotations

import logging

import pytest

from app.models import ThunderLevel
from output.metric_format import thunder_ordinal
from output.renderers.compare_metric_catalog import get_compare_metric_catalog
from output.renderers.compare_metric_ids import (
    FRONTEND_TO_RENDERER_METRIC_ID,
    resolve_enabled_metrics,
)
from output.renderers.email.compare_html import CV2_METRICS


def test_unmapped_metric_logs_warning_instead_of_silent_drop(caplog):
    """AC-6 (rot vor Fix): ``resolve_enabled_metrics()`` verwirft eine nicht
    mappbare ID heute kommentarlos -- kein Log-Warning wird erzeugt.
    """
    with caplog.at_level(logging.WARNING):
        resolve_enabled_metrics(["nicht_gemappte_id_xyz"])

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, (
        "resolve_enabled_metrics() verwirft eine nicht mappbare ID heute "
        "kommentarlos -- kein Log-Warning erzeugt (AC-6 struktureller Guard "
        "fehlt)."
    )
    assert any("nicht_gemappte_id_xyz" in r.getMessage() for r in warnings), (
        f"Kein Warning nennt die verworfene ID 'nicht_gemappte_id_xyz': "
        f"{[r.getMessage() for r in warnings]}"
    )


def _cv2_renderer_keys() -> set[str]:
    """CV2_METRICS-Keys ohne die feste "warn"-Zeile (keine Katalog-Metrik,
    sondern die amtlichen Warnungen -- s. Spec Known Limitations)."""
    return {m["key"] for m in CV2_METRICS if m["key"] != "warn"}


def test_all_catalog_metrics_have_cv2_render_row():
    """Struktureller Guard: JEDE im Backend-Katalog gefuehrte, waehlbare
    Compare-Metrik-ID braucht eine CV2_METRICS-Renderzeile in der Mail.
    Schlaegt fehl, sobald eine neu eingefuehrte Katalog-Metrik ohne
    zugehoerige Mail-Zeile hinzukommt (der Bug-Typ von #1285/#1296/#1324).
    Keine hartkodierte Anzahl -- Mengen-Vergleich, kein ``== N``.
    """
    catalog_keys = {entry["key"] for entry in get_compare_metric_catalog()}
    renderer_ids_from_catalog = {
        FRONTEND_TO_RENDERER_METRIC_ID[k]
        for k in catalog_keys
        if k in FRONTEND_TO_RENDERER_METRIC_ID
    }
    cv2_keys = _cv2_renderer_keys()

    missing = renderer_ids_from_catalog - cv2_keys
    assert not missing, (
        f"Katalog-Metriken ohne CV2_METRICS-Zeile (werden in der Mail still "
        f"verworfen statt angezeigt): {sorted(missing)}"
    )

    orphaned = cv2_keys - renderer_ids_from_catalog
    assert not orphaned, (
        f"CV2_METRICS enthaelt Zeilen ohne Katalog-Ursprung (verwaiste "
        f"Renderzeile, Katalog veraltet?): {sorted(orphaned)}"
    )


def test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row():
    """Wirkungsnachweis (analog #1298 B3): haelt den Kern-Vergleich aus
    ``test_all_catalog_metrics_have_cv2_render_row`` gegen KUENSTLICH um eine
    CV2-Zeile reduzierte Kopien der Daten -- simuliert eine neue Katalog-
    Metrik, die (wie bei #1285/#1296/#1324) keine Renderzeile in der Mail
    bekommen hat. Arbeitet auf Kopien, mutiert keine Produktivdaten.
    """
    catalog_keys = {entry["key"] for entry in get_compare_metric_catalog()}
    renderer_ids_from_catalog = {
        FRONTEND_TO_RENDERER_METRIC_ID[k]
        for k in catalog_keys
        if k in FRONTEND_TO_RENDERER_METRIC_ID
    }
    real_cv2_keys = _cv2_renderer_keys()

    # Vorbedingung: die echten Daten sind heute konsistent (kein bestehender
    # Drift, den dieser Test nur zufaellig aufdecken wuerde).
    assert renderer_ids_from_catalog - real_cv2_keys == set(), (
        "Vorbedingung verletzt: echte Katalog-/CV2-Daten sind bereits "
        "inkonsistent -- Wirkungsnachweis nicht aussagekraeftig."
    )

    # Kuenstlich reduzierte Kopie: eine CV2-Zeile "fehlt" (simuliert eine neue
    # Katalog-Metrik ohne Renderzeile).
    removed_key = next(iter(real_cv2_keys))
    reduced_cv2_keys = real_cv2_keys - {removed_key}

    missing = renderer_ids_from_catalog - reduced_cv2_keys
    assert missing == {removed_key}, (
        f"Guard-Vergleich erkennt die kuenstlich entfernte Zeile "
        f"'{removed_key}' nicht als fehlend -- Wirkungsnachweis "
        f"fehlgeschlagen: missing={missing}"
    )

    # Derselbe Assert-Ausdruck wie im echten Guard-Test muss gegen die
    # kuenstlich reduzierten Daten tatsaechlich einen AssertionError werfen.
    with pytest.raises(AssertionError):
        assert not missing, (
            f"Katalog-Metriken ohne CV2_METRICS-Zeile (werden in der Mail "
            f"still verworfen statt angezeigt): {sorted(missing)}"
        )


def _thunder_catalog_entry() -> dict:
    return next(
        e for e in get_compare_metric_catalog() if e["key"] == "thunder_level_max"
    )


def test_thunder_ordinal_labels_cover_every_thunder_level():
    """Struktureller Guard (#1474 Adversary-Fund F001): die Beschriftungsliste
    des Ortsvergleichs-Schiebereglers fuer ``thunder_level_max`` (kind=
    "ordinal") muss GENAUSO viele Eintraege haben wie ``ThunderLevel`` Werte
    UND ihre Reihenfolge muss der Ordinalreihenfolge aus ``thunder_ordinal()``
    entsprechen -- sonst leitet das Frontend
    (compareMetricCatalogLoader.ts::buildCompareMetricDefs, Scale =
    ``[0, len(ordinalLabels) - 1]``) eine zu kurze Schieberegler-Spanne ab:
    die hoechste Stufe waere nicht waehlbar, eine mittlere loest zu frueh aus.

    Erwartung wird AUS ``ThunderLevel``/``thunder_ordinal()`` abgeleitet, NICHT
    aus einer zweiten hartcodierten Liste -- sonst prueft der Test nur sich
    selbst und faengt keine zukuenftige neue Stufe.
    """
    entry = _thunder_catalog_entry()
    assert entry["kind"] == "ordinal"

    all_levels = list(ThunderLevel)
    expected_count = len(all_levels)
    labels = entry["ordinalLabels"]

    assert len(labels) == expected_count, (
        f"ordinalLabels hat {len(labels)} Eintraege, ThunderLevel kennt aber "
        f"{expected_count} Werte {all_levels} -- der Schieberegler kann nicht "
        f"jede Stufe erreichen (F001)."
    )

    # thunder_ordinal() muss jeden ThunderLevel-Wert luecken- und
    # ueberschneidungsfrei auf genau einen Index 0..expected_count-1 abbilden
    # -- das IST die Reihenfolge, der ordinalLabels folgen muss (Index i ==
    # das Level mit thunder_ordinal(level) == i).
    ordinals = sorted(thunder_ordinal(level) for level in all_levels)
    assert ordinals == list(range(expected_count)), (
        f"thunder_ordinal() liefert keine lueckenfreie 0..{expected_count - 1}"
        f"-Ordnung ueber alle ThunderLevel-Werte: "
        f"{[(l, thunder_ordinal(l)) for l in all_levels]}"
    )


def test_guard_actually_fails_when_ordinal_labels_are_too_short():
    """Wirkungsnachweis (analog #1298 B3 / #1350): haelt den Kern-Vergleich aus
    ``test_thunder_ordinal_labels_cover_every_thunder_level`` gegen eine
    kuenstlich um einen Eintrag verkuerzte Kopie -- simuliert exakt den
    Adversary-Fund F001 (drei Labels statt vier nach der Ordinalverschiebung
    durch ThunderLevel.LOW). Mutiert keine Produktivdaten.
    """
    all_levels = list(ThunderLevel)
    expected_count = len(all_levels)

    # Vorbedingung: die echten Daten sind heute konsistent.
    real_labels = _thunder_catalog_entry()["ordinalLabels"]
    assert len(real_labels) == expected_count, (
        "Vorbedingung verletzt: der echte Katalog-Eintrag ist bereits "
        "inkonsistent -- Wirkungsnachweis nicht aussagekraeftig."
    )

    truncated_labels = real_labels[:-1]
    with pytest.raises(AssertionError):
        assert len(truncated_labels) == expected_count, (
            f"ordinalLabels hat {len(truncated_labels)} Eintraege, "
            f"ThunderLevel kennt aber {expected_count} Werte -- der "
            f"Schieberegler kann nicht jede Stufe erreichen (F001)."
        )
