# doc-compliance-test
# PARITAET-BEGRUENDUNG: Prueft die Vollstaendigkeit der Kataloge de und en im Bereich api, es gibt keinen Doppelcode, nur zwei Sprachdateien.
"""Katalogbereich ``api``: Schluessel- und Platzhalterparitaet (Issue #2674, AC-7).

SPEC: docs/specs/modules/i18n_p11_api_meldungen_ratsche_2674.md AC-7.

Daten-Check auf den Katalogdateien (kein Verhaltensnachweis). Die Anker-
Tabelle unten ist die Codes-/Skalentabelle der Spec: ``de`` ist der Text der
Ist-Fassung (``git show origin/main:<datei>``, Stand 2175114cd), ``en`` laut
Spec/Glossar.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KATALOG = REPO / "src" / "i18n" / "messages"

ANKER: dict[str, tuple[str, str]] = {
    "api.fehler.trip_nicht_gefunden": (
        "Trip {trip_id} nicht gefunden für User {user_id}",
        "Trip {trip_id} not found for user {user_id}"),
    "api.fehler.vorschau_trip_nicht_gefunden": (
        "Trip '{trip_id}' nicht gefunden für user '{user_id}'",
        "Trip '{trip_id}' not found for user '{user_id}'"),
    "api.fehler.vorschau_ohne_wegpunkte": (
        "Trip '{trip_id}' hat keine Etappe mit genug waypoints für eine Vorschau",
        "Trip '{trip_id}' has no stage with enough waypoints for a preview"),
    "api.fehler.vorschau_etappe_fehlt": (
        "Keine Stage am {datum} im Trip '{trip_id}'",
        "No stage on {datum} in trip '{trip_id}'"),
    "api.fehler.vorschau_zu_wenige_wegpunkte": (
        "Stage am {datum} im Trip '{trip_id}' hat zu wenige waypoints für eine Vorschau",
        "Stage on {datum} in trip '{trip_id}' has too few waypoints for a preview"),
    "api.fehler.vorschau_ohne_etappen": (
        "Trip '{trip_id}' hat keine Stages", "Trip '{trip_id}' has no stages"),
    "api.fehler.vorschau_wetter_fehlt": (
        "Wetterdaten nicht verfügbar für Trip '{trip_id}' am {datum}",
        "Weather data not available for trip '{trip_id}' on {datum}"),
    "api.fehler.vorschau_datum_ungueltig": (
        "Ungültiges Datum '{datum}', ISO erwartet",
        "Invalid date '{datum}', ISO format expected"),
    "api.fehler.report_typ_ungueltig": (
        "Ungültiger report_type '{report_type}'", "Invalid report_type '{report_type}'"),
    "api.fehler.typ_ungueltig": ("Ungültiger type '{type}'", "Invalid type '{type}'"),
    "api.fehler.body_genau_einer": (
        "Body muss genau einen von 'onset', 'changes', 'official' oder 'nowcast_frames' enthalten",
        "Body must contain exactly one of 'onset', 'changes', 'official' or 'nowcast_frames'"),
    "api.fehler.segment_unbekannt": (
        "Unbekannte segment_id '{segment_id}' im Trip",
        "Unknown segment_id '{segment_id}' in the trip"),
    "api.fehler.metrik_unbekannt": (
        "Unbekannte Metrik '{metric}' in changes", "Unknown metric '{metric}' in changes"),
    "api.fehler.alarm_body_ungueltig": (
        "Ungültiger Alarm-Körper: {grund}", "Invalid alert body: {grund}"),
    "api.fehler.vergleich_nicht_gefunden": (
        "Orts-Vergleich '{preset_id}' nicht gefunden für Nutzer '{user_id}'",
        "Location comparison '{preset_id}' not found for user '{user_id}'"),
    "api.fehler.vergleich_ohne_orte": (
        "Orts-Vergleich '{preset_id}' hat keine Orte konfiguriert — es gibt nichts zu vergleichen.",
        "Location comparison '{preset_id}' has no locations configured - there is nothing to compare."),
    "api.fehler.vergleich_orte_geloescht": (
        "Ortsvergleich '{preset_id}' verweist auf gelöschte Orte. Ersetze die Orte im "
        "Ortsvergleich. (Orte {location_ids} nicht aufloesbar)",
        "Location comparison '{preset_id}' points to deleted locations. Replace the locations "
        "in the comparison. (Locations {location_ids} not resolvable)"),
    "api.fehler.vergleich_datum_ungueltig": (
        "Ungültiges Datum '{datum}' (erwartet ISO JJJJ-MM-TT)",
        "Invalid date '{datum}' (expected ISO YYYY-MM-DD)"),
    "api.fehler.vergleich_body_genau_einer": (
        "Body muss genau einen von 'changes', 'onsets' oder 'official' enthalten",
        "Body must contain exactly one of 'changes', 'onsets' or 'official'"),
    "api.fehler.vergleich_orte_fremd": (
        "Orte {orte} gehoeren nicht zu diesem Orts-Vergleich",
        "Locations {orte} do not belong to this location comparison"),
    "api.fehler.vergleich_keine_warnung": (
        "Keine amtliche Warnung fuer die Orte dieses Vergleichs",
        "No official warning for the locations of this comparison"),
    "api.fehler.gpx_nur_gpx": (
        "Nur .gpx Dateien erlaubt, nicht '{filename}'",
        "Only .gpx files are allowed, not '{filename}'"),
    "api.fehler.gpx_zu_gross": (
        "Die GPX-Datei ist zu groß (höchstens {max_mb} MB).",
        "The GPX file is too large (at most {max_mb} MB)."),
    "api.fehler.gpx_speicher_voll": (
        "Dein GPX-Speicher ist voll (höchstens {max_dateien} Dateien und {max_mb} MB). Lade eine Datei mit gleichem Namen hoch, um sie zu ersetzen.",
        "Your GPX storage is full (at most {max_dateien} files and {max_mb} MB). Upload a file with the same name to replace it."),
    "api.fehler.gpx_ungueltig": (
        "Die GPX-Datei konnte nicht gelesen werden: Sie ist leer, beschädigt oder enthält keinen verwertbaren Track (mindestens 10 Punkte).",
        "The GPX file could not be read: it is empty, damaged or contains no usable track (at least 10 points)."),
    "api.fehler.wetterdienst_fehler": (
        "Der Wetterdienst ist gerade nicht erreichbar. Bitte versuche es später erneut.",
        "The weather service is currently unavailable. Please try again later."),
    "api.fehler.unbekannt": (
        "Die Anfrage konnte nicht verarbeitet werden.",
        "The request could not be processed."),
    # Issue #2961 (ADR-0117): interaktives Abruf-Kontingent und Eingabegrenzen.
    "api.fehler.abruf_kontingent_erschoepft": (
        "Dein Kontingent für Wetterabfragen ist für heute aufgebraucht, und für diese Anfrage liegen keine zwischengespeicherten Daten vor. Ab Mitternacht (UTC) geht es wieder. Geplante Briefings und Alarme laufen unverändert weiter.",
        "Your weather request quota for today is used up, and no cached data is available for this request. It resets at midnight (UTC). Scheduled briefings and alerts continue as usual."),
    "api.fehler.etappenwetter_teilweise": (
        "Für einige Etappen gibt es heute keine Wetterdaten mehr, weil dein Kontingent für Wetterabfragen aufgebraucht ist. Ab Mitternacht (UTC) geht es wieder.",
        "Some stages have no weather data today because your weather request quota is used up. It resets at midnight (UTC)."),
    "api.fehler.vergleich_parameter_ungueltig": (
        "Ungültige Angabe für {parameter}: erlaubt ist {erlaubt}.",
        "Invalid value for {parameter}: allowed is {erlaubt}."),
    "api.skala.wind.schwach": ("schwach", "weak"),
    "api.skala.wind.maessig": ("mäßig", "moderate"),
    "api.skala.wind.stark": ("stark", "strong"),
    "api.skala.wind.sehr_stark": ("sehr stark", "very strong"),
    "api.skala.niederschlag.trocken": ("trocken", "dry"),
    "api.skala.niederschlag.leicht": ("leicht", "light"),
    "api.skala.niederschlag.maessig": ("mäßig", "moderate"),
    "api.skala.niederschlag.stark": ("stark", "heavy"),
    "api.skala.regen.unwahrscheinlich": ("unwahrscheinlich", "unlikely"),
    "api.skala.regen.moeglich": ("möglich", "possible"),
    "api.skala.regen.wahrscheinlich": ("wahrscheinlich", "likely"),
    "api.skala.regen.sehr_wahrscheinlich": ("sehr wahrscheinlich", "very likely"),
    "api.skala.sonne.truebe": ("trübe", "overcast"),
    "api.skala.sonne.wechselhaft": ("wechselhaft", "changeable"),
    "api.skala.sonne.freundlich": ("freundlich", "fair"),
    "api.skala.sonne.sonnig": ("sonnig", "sunny"),
}


def _bereich(lang: str) -> dict[str, str]:
    return json.loads((KATALOG / lang / "api.json").read_text(encoding="utf-8"))


def test_api_schluessel_und_platzhalter_paritaet():
    from i18n.catalog import parity_errors

    de, en = _bereich("de"), _bereich("en")
    assert set(de) == set(en)
    assert [f for f in parity_errors(KATALOG)
            if f.startswith(("api", "de/api", "en/api"))] == []


@pytest.mark.parametrize("key", sorted(ANKER))
def test_ankertext_je_sprache(key):
    de, en = ANKER[key]
    assert _bereich("de").get(key) == de
    assert _bereich("en").get(key) == en


def test_katalog_traegt_genau_die_anker():
    assert set(_bereich("de")) == set(ANKER)
