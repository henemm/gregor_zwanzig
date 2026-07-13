"""ASCII-Faltung statt Zeichen-Loeschung — Issue #1253.

SPEC: docs/specs/modules/fix_1252_1253_kanal_text.md (AC-3, AC-4, AC-5, AC-7,
      AC-8)
KONTEXT: docs/context/fix-1252-1253-kanal-text-v2.md

RED-Phase: `src/utils/ascii_fold.py::fold_ascii` existiert noch nicht -> jeder
Test, der es importiert, schlaegt mit ImportError fehl (lokaler Import je
Testfunktion, damit jeder Test seinen eigenen, klaren RED-Grund traegt statt
eines einzigen Modul-Collection-Fehlers).

Die Renderer-Pfad-Tests (SMS/E-Mail/`_sms_stage_prefix`) brauchen `fold_ascii`
NICHT zum Reproduzieren des Bugs — sie belegen den heutigen Fehler direkt am
bestehenden `_ascii()`/`_ASCII_MAP`-Code (`encode('ascii','ignore')` bzw.
fehlende Umlaut-Behandlung), der Akzent-/Umlaut-Buchstaben ersatzlos loescht
statt sie zu falten (`Hyères` -> `Hyres`, `München` -> `Mnchen`).

Mock-frei: echte Renderer-Aufrufe, echte Domain-Objekte (`OfficialAlert`,
`AlertMessage`, `OnsetEvent`, Fake-Trip/-Segment mit den vom Aufrufer
benoetigten Attributen statt vollem Fixture-Aufbau).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

UTC = timezone.utc


# ---------------------------------------------------------------------------
# fold_ascii() selbst — Reihenfolge Umlaut-Map VOR NFKD ist die Pointe
# ---------------------------------------------------------------------------


def test_fold_ascii_folds_french_accent():
    """AC-3 (Grundlage): Given `Hyères` / When `fold_ascii` aufgerufen wird /
    Then ist das Ergebnis `Hyeres` (Akzent gefaltet, nicht geloescht)."""
    from utils.ascii_fold import fold_ascii

    assert fold_ascii("Hyères") == "Hyeres", (
        "fold_ascii muss den Akzent falten (NFKD + Combining-Marks entfernen), "
        "nicht den Buchstaben ersatzlos loeschen"
    )


def test_fold_ascii_umlaut_digraph_before_nfkd():
    """AC-4 (Reihenfolge-Beweis): Given `München` / When `fold_ascii`
    aufgerufen wird / Then ist das Ergebnis `Muenchen`, NICHT `Munchen` --
    eine NFKD-ZUERST-Implementierung wuerde `ü` zu `u` zerlegen statt zur
    `ue`-Digraph-Map zu falten (sms_format.md:27 bindend: ae/oe/ue/ss)."""
    from utils.ascii_fold import fold_ascii

    result = fold_ascii("München")
    assert result == "Muenchen", (
        f"fold_ascii muss die Umlaut-Digraph-Map VOR der NFKD-Normalisierung "
        f"anwenden -- 'München' -> 'Muenchen' erwartet, erhalten: {result!r}"
    )
    assert result != "Munchen", (
        "fold_ascii hat NFKD vor der Umlaut-Map angewendet (falsche "
        "Reihenfolge) -- 'ü' wurde zu 'u' statt zu 'ue' zerlegt"
    )


def test_fold_ascii_all_umlauts_and_eszett():
    """Non-Regression/Vollstaendigkeit: alle vier Digraph-Faelle aus
    sms_format.md:27 (ä->ae, ö->oe, ü->ue, ß->ss), Gross- und Kleinschreibung."""
    from utils.ascii_fold import fold_ascii

    assert fold_ascii("äöüÄÖÜß") == "aeoeueAeOeUess"


# ---------------------------------------------------------------------------
# AC-3/AC-4 — echter SMS-Renderer-Pfad (Official-Alert-Warnungen)
# ---------------------------------------------------------------------------


def _compare_notices_for_single_location(raw_name: str):
    """Baut EINE `OfficialAlertNotice` ueber den echten Compare-Builder, mit
    einem rohen (nicht vorgefalteten) Ortsnamen -- exakt der reale
    Staging-Fall (Hyères/Fréjus/Collobrières, GR20/Korsika/Frankreich)."""
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="vigilance", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=None, valid_to=None, region_label="Var",
    )
    ids = ["a", "b"]
    names = {"a": raw_name, "b": "Autre Ville"}
    return build_compare_official_alert_notices(ids, names, [(alert, ["a"])])


def test_official_alert_sms_folds_accented_location_hyeres():
    """AC-3: Given eine Warnung betrifft `Hyères` / When die SMS gerendert
    wird (`render_official_alert_sms`, der ECHTE Versand-Renderer) / Then
    enthaelt die SMS `Hyeres`, NICHT das verstuemmelte `Hyres`."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    notices = _compare_notices_for_single_location("Hyères")
    sms = render_official_alert_sms(notices, sms_prefix="GZ", tz=UTC)

    assert "Hyeres" in sms, f"Gefaltetes 'Hyeres' fehlt in der SMS: {sms!r}"
    assert "Hyres" not in sms, (
        f"SMS enthaelt weiterhin die verstuemmelte Form 'Hyres' (Buchstabe "
        f"ersatzlos geloescht statt gefaltet): {sms!r}"
    )
    assert sms.isascii(), f"SMS muss reines ASCII/GSM-7 bleiben: {sms!r}"
    assert len(sms) <= 140, f"SMS ueberschreitet das 140-Zeichen-Limit: {len(sms)}"


def test_official_alert_sms_folds_umlaut_location_muenchen():
    """AC-4: Given eine Warnung betrifft `München` / When die SMS gerendert
    wird / Then enthaelt die SMS `Muenchen`, NICHT `Mnchen`."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    notices = _compare_notices_for_single_location("München")
    sms = render_official_alert_sms(notices, sms_prefix="GZ", tz=UTC)

    assert "Muenchen" in sms, f"Gefaltetes 'Muenchen' fehlt in der SMS: {sms!r}"
    assert "Mnchen" not in sms, (
        f"SMS enthaelt weiterhin die verstuemmelte Form 'Mnchen': {sms!r}"
    )
    assert sms.isascii(), f"SMS muss reines ASCII/GSM-7 bleiben: {sms!r}"
    assert len(sms) <= 140, f"SMS ueberschreitet das 140-Zeichen-Limit: {len(sms)}"


# ---------------------------------------------------------------------------
# AC-5 — echter E-Mail-Klartext-Renderer (compact.py)
# ---------------------------------------------------------------------------


def test_compact_email_plaintext_folds_accented_trip_name():
    """AC-5: Given ein Trip-Name mit Akzent (`Hyères`) / When der
    E-Mail-Klartext gerendert wird (`render_compact`) / Then erscheint der
    gefaltete, lesbare Name `Hyeres` statt eines verstuemmelten Namens --
    die Akzent-Faltung fehlte bislang auch im E-Mail-Klartext (nur die
    Umlaut-Map war vorhanden, Akzente wurden weiter geloescht)."""
    from zoneinfo import ZoneInfo

    from app.metric_catalog import build_default_display_config
    from output.renderers.email.compact import render_compact
    from tests.unit.test_renderers_email import _make_segment_weather

    seg = _make_segment_weather()
    plain = render_compact(
        segments=[seg],
        dc=build_default_display_config(),
        multi_day_trend=None,
        stability_result=None,
        tz=ZoneInfo("UTC"),
        report_type="evening",
        trip_name="Hyères",
        stage_name=None,
        stage_stats=None,
    )

    assert "Hyeres" in plain, (
        f"Gefaltetes 'Hyeres' fehlt im E-Mail-Klartext: {plain!r}"
    )
    assert "Hyres" not in plain, (
        f"E-Mail-Klartext enthaelt weiterhin die verstuemmelte Form 'Hyres': {plain!r}"
    )
    assert plain.isascii(), f"Kompakter E-Mail-Body muss ASCII-only sein: {plain!r}"


# ---------------------------------------------------------------------------
# AC-3/AC-4 (Nachzug) — `sms_trip.py::_sms_stage_prefix` faltet heute GAR NICHT
# ---------------------------------------------------------------------------


def test_sms_stage_prefix_folds_umlaut_stage_name():
    """Given ein Etappenname mit Umlaut (`München`, kein 'Etappe N:'-Muster)
    / When `_sms_stage_prefix` den SMS-Kopf-Praefix baut / Then ist das
    Ergebnis gefaltet (`Muenchen`), NICHT der rohe Name mit Umlaut --
    `_sms_stage_prefix` schneidet heute nur roh auf 10 Zeichen (`[:10]`), ohne
    jede Faltung."""
    from output.renderers.sms_trip import _sms_stage_prefix

    result = _sms_stage_prefix("München")
    assert result == "Muenchen", (
        f"Etappenname mit Umlaut wird nicht gefaltet: {result!r} (erwartet 'Muenchen')"
    )
    assert result.isascii(), f"SMS-Etappen-Praefix muss ASCII sein: {result!r}"


# ---------------------------------------------------------------------------
# AC-7 — Doppelkuerzung: roh vorgekuerzter `trip_short` frisst Buchstaben
# ---------------------------------------------------------------------------


class _FakeTripForRadar:
    def __init__(self, name: str) -> None:
        self.name = name
        self.alert_cooldown_minutes = None


class _FakePoint:
    def __init__(self, lat: float, lon: float) -> None:
        self.lat = lat
        self.lon = lon


class _FakeActiveSegment:
    def __init__(self) -> None:
        self.start_point = _FakePoint(47.0, 11.0)
        self.distance_km = 5.0


def test_radar_alert_trip_short_survives_double_truncation():
    """AC-7: Given ein Trip-Name mit Umlaut nahe der 16-Zeichen-Grenze
    (`Wandergruppe München`) / When der SMS-Titelzeilen-Pfad ueber
    `radar_alert_service.py::build_onset_alert_message` (roh vorgekuerztes
    `trip.name[:16]`, Zeile 71) UND den kanonischen SMS-Renderer laeuft /
    Then entspricht das Ergebnis `fold_ascii(trip.name)[:16]` -- ERST falten,
    DANN kuerzen (sms_format.md:66), statt der heutigen Doppelkuerzung (roh
    kuerzen, dann falten, dann nochmal kuerzen), die Buchstaben frisst, weil
    'ü' -> 'ue' beim Falten waechst."""
    from output.renderers.alert.render import render_sms
    from services.radar_alert_service import build_onset_alert_message
    from utils.ascii_fold import fold_ascii

    trip = _FakeTripForRadar("Wandergruppe München")
    active = _FakeActiveSegment()

    msg = build_onset_alert_message(
        trip, active, onset_minutes=12, onset_time="14:00",
        intensity_label="leichter Regen", source_label="Radar",
    )
    sms = render_sms(msg)
    expected_prefix = fold_ascii(trip.name)[:16].rstrip(" (-_")

    assert sms.startswith(expected_prefix), (
        f"Doppelkuerzung verstuemmelt den Trip-Namen mitten im Wort: "
        f"SMS={sms!r} erwarteter Kopf={expected_prefix!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Guard: SMS bleibt ASCII/GSM-7 und <=160 Zeichen bei Sonderzeichen
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Adversary-Finding F001 -- eigenstaendige Codepoints, die NFKD NICHT in
# Basis+Combining-Mark zerlegt (im Gegensatz zu z.B. 'å' -> 'a' + Ring, das
# NFKD bereits korrekt handhabt), verschwinden ohne explizite Map ersatzlos.
# ---------------------------------------------------------------------------


def test_fold_ascii_folds_nordic_o_slash():
    """F001 (v2: `anyascii`-Ergebnis statt handgepflegter Tabelle): Given
    `Tromsø` / When `fold_ascii` aufgerufen wird / Then bleibt der Ort
    wiedererkennbar (Praefix `Tromso`) -- `ø` darf nicht ersatzlos
    verschwinden, `anyascii` liefert `Tromso` statt der frueheren
    Digraph-Form `Tromsoe`, beides ist auffindbar."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Tromsø")
    assert folded.startswith("Tromso"), (
        f"'ø' darf nicht ersatzlos verschwinden: {folded!r}"
    )
    assert folded.isascii()


def test_fold_ascii_folds_polish_l_stroke_and_z_acute():
    """F001: Given `Łódź` / When `fold_ascii` aufgerufen wird / Then ist das
    Ergebnis `Lodz` -- `Ł` wird von NFKD NICHT zerlegt, `ó`/`ź` dagegen
    schon (Basis+Combining-Akut) und werden bereits korrekt gefaltet."""
    from utils.ascii_fold import fold_ascii

    assert fold_ascii("Łódź") == "Lodz", (
        f"'Ł' darf nicht ersatzlos verschwinden: {fold_ascii('Łódź')!r}"
    )


def test_fold_ascii_folds_ae_ligature():
    """F001 (v2: `anyascii`-Ergebnis statt handgepflegter Tabelle): Given
    `Ærø` / When `fold_ascii` aufgerufen wird / Then ist der Ort
    wiedererkennbar (`Aero`) -- sowohl `Æ` als auch `ø` sind eigenstaendige
    Codepoints ohne NFKD-Zerlegung und duerfen nicht ersatzlos
    verschwinden."""
    from utils.ascii_fold import fold_ascii

    assert fold_ascii("Ærø") == "Aero", (
        f"'Æ' und 'ø' duerfen nicht ersatzlos verschwinden: {fold_ascii('Ærø')!r}"
    )


def test_fold_ascii_never_silently_drops_letters():
    """F001-Generik-Guard (Adversary-Runde 2 F002, VERSCHAERFT; Runde 3
    PO-Auftrag 2026-07-13 nochmals VERSCHAERFT auf Zeichen-Ebene; Runde 4
    PO-Auftrag 2026-07-13 nochmals VERSCHAERFT um die Kategorien Lo/Lm): eine
    reine Gesamtlaengen- oder Wortanzahl-Schwelle uebersieht den Verlust
    EINZELNER Buchstaben INNERHALB eines Wortes -- `Ђердап` -> `erdap` (das
    fuehrende `Ђ` verschwindet ersatzlos) bestand den alten wort-basierten
    Waechter anstandslos, weil die Wortanzahl (1) und die Laenge (5 von 6
    Zeichen, > 50%) unauffaellig blieben. Deshalb jetzt zusaetzlich PRO
    ZEICHEN: jedes Buchstaben-Zeichen (Unicode-Kategorie Ll/Lu/Lt/Lo/Lm) der
    Eingabe MUSS, einzeln durch `fold_ascii` geschickt, mindestens ein
    ASCII-Zeichen beitragen -- sonst wurde es beim Falten des Gesamtwortes
    still geloescht. Lo (Buchstabe ohne Gross-/Kleinschreibung, z.B. arabisch)
    und Lm (modifizierender Buchstabe) fehlten bis Runde 4 in dieser Pruefung
    -- exakt darin lag der Adversary-Fund F001 (`ا` ARABIC LETTER ALEF,
    Kategorie Lo, faltet bei `anyascii` zu leerem String). Die alten Wort-/
    Laengen-Pruefungen bleiben als zusaetzliches Netz erhalten."""
    import unicodedata

    from utils.ascii_fold import fold_ascii

    names = [
        "Tromsø", "Łódź", "Ærø", "Malmö", "Świnoujście", "København",
        "Kavala Καβάλα District", "Θεσσαλονίκη", "София", "Пловдив", "Київ",
        "Ђердап", "Ħamrun", "Слаўгарад", "Ѓорче", "Варна", "Şanlıurfa",
        "ا",
    ]
    for name in names:
        folded = fold_ascii(name)
        assert folded.isascii(), f"{name!r} -> {folded!r} ist nicht ASCII"
        # Kein Name darf auf weniger als die Haelfte seiner urspruenglichen
        # Laenge schrumpfen -- Digraph-Faltung (oe/ae/th/...) VERGROESSERT
        # eher, ersatzloses Loeschen von Buchstaben SCHRUMPFT drastisch.
        assert len(folded) >= len(name) // 2, (
            f"{name!r} ist auf {folded!r} geschrumpft -- Buchstaben wurden "
            f"vermutlich still geloescht statt gefaltet"
        )
        assert folded.strip(), f"{name!r} -> {folded!r} ist (fast) leer"
        # F002-Verschaerfung: Wort-fuer-Wort statt Gesamtlaenge.
        original_words = name.split()
        folded_words = folded.split()
        assert len(folded_words) == len(original_words), (
            f"{name!r} -> {folded!r}: Wortanzahl geaendert "
            f"({len(original_words)} -> {len(folded_words)}) -- ein Wort ist "
            f"vermutlich komplett verschwunden statt gefaltet zu werden"
        )
        assert all(w for w in folded_words), (
            f"{name!r} -> {folded!r}: mindestens ein Wort wurde zur leeren "
            f"Zeichenkette"
        )
        assert "  " not in folded, (
            f"{name!r} -> {folded!r}: Doppel-Leerzeichen deutet auf ein "
            f"komplett verschwundenes Wort hin"
        )
        # Runde-3-Verschaerfung (Runde 4: Lo/Lm ergaenzt): zeichenweiser
        # Beweis -- jedes Buchstaben-Zeichen fuer sich genommen darf nicht
        # zu leerem ASCII falten.
        for ch in name:
            if unicodedata.category(ch) in ("Ll", "Lu", "Lt", "Lo", "Lm"):
                folded_char = fold_ascii(ch)
                assert folded_char, (
                    f"Buchstabe {ch!r} (aus {name!r}) faltet einzeln zu "
                    f"leerem String -- wird innerhalb des Wortes still "
                    f"geloescht statt gefaltet"
                )


def test_fold_ascii_serbian_djerdap_keeps_leading_letter():
    """PO-Auftrag 2026-07-13 (Adversary-Fund, Runde 3): Given `Ђердап`
    (serbischer Ortsname, kyrillisches Schriftsystem ohne Serbisch-Eintrag
    in der ALTEN handgepflegten `_CYRILLIC_MAP`) / When `fold_ascii`
    aufgerufen wird / Then enthaelt das Ergebnis `Djerdap`, NICHT das
    verstuemmelte `erdap` (fuehrender Buchstabe `Ђ` ersatzlos geloescht)."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Ђердап")
    assert "Djerdap" in folded, (
        f"Serbischer Ortsname muss vollstaendig transliteriert werden, "
        f"nicht am Wortanfang verstuemmelt: {folded!r}"
    )
    assert "erdap" != folded, (
        f"'Ђердап' darf NICHT zu 'erdap' verstuemmelt werden (fuehrender "
        f"Buchstabe geloescht): {folded!r}"
    )
    assert folded.isascii()


def test_fold_ascii_maltese_hamrun():
    """PO-Auftrag 2026-07-13: Given `Ħamrun` (Malta, MeteoAlarm-Mitglied,
    `ħ` war in KEINER alten Tabelle) / When `fold_ascii` aufgerufen wird /
    Then enthaelt das Ergebnis `Hamrun`."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Ħamrun")
    assert "Hamrun" in folded, f"Maltesischer Ortsname verstuemmelt: {folded!r}"
    assert folded.isascii()


def test_fold_ascii_single_serbian_letter_not_empty():
    """PO-Auftrag 2026-07-13: Given das einzelne Zeichen `Ђ` (kein
    zusammengesetztes Wort) / When `fold_ascii` aufgerufen wird / Then ist
    das Ergebnis NICHT leer -- exakt der Fall, den der alte wort-/laengen-
    basierte Waechter nicht zeichenweise nachweisen konnte."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Ђ")
    assert folded, "Einzelner Buchstabe 'Ђ' faltet zu leerem String"
    assert folded.isascii()


def test_fold_ascii_mixed_greek_latin_no_word_disappears():
    """F002 (MEDIUM) Gegenbeispiel aus dem Adversary-Finding woertlich:
    Given `Kavala Καβάλα District` / When `fold_ascii` aufgerufen wird /
    Then bleiben alle DREI Woerter erhalten (der griechische Ortsname wird
    transliteriert, nicht geloescht) -- die alte Gesamtlaengen-Pruefung liess
    genau diesen Fall durchrutschen (72% Laengenerhalt trotz komplett
    verschwundenem mittleren Wort)."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Kavala Καβάλα District")
    words = folded.split()
    assert len(words) == 3, (
        f"Ein Wort ist verschwunden: {folded!r} hat nur {len(words)} statt 3 "
        f"Woerter"
    )
    assert "  " not in folded, f"Doppel-Leerzeichen in {folded!r}"
    assert folded.isascii()


def test_official_alert_sms_stays_ascii_and_within_limit_with_special_chars():
    """AC-8: Given eine SMS mit gefalteten Sonderzeichen (Ortsname mit
    Akzent) UND Vigilance-Token / When die SMS final zusammengesetzt wird /
    Then bleibt sie <=160 Zeichen und rein ASCII (`sms.isascii()`)."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    notices = _compare_notices_for_single_location("Hyères")
    sms = render_official_alert_sms(notices, sms_prefix="GZ", limit=160, tz=UTC)

    assert sms.isascii(), f"SMS ist nicht rein ASCII/GSM-7: {sms!r}"
    assert len(sms) <= 160, f"SMS ueberschreitet 160 Zeichen: {len(sms)} — {sms!r}"


# ---------------------------------------------------------------------------
# Adversary-Finding F001 (Runde 2, CRITICAL) -- griechische/kyrillische
# Ortsnamen verschwinden KOMPLETT (weder Umlaut-Map noch NFKD zerlegbar),
# eine amtliche Warnung erscheint dann OHNE Ortsangabe.
# ---------------------------------------------------------------------------


def test_fold_ascii_folds_greek_thessaloniki():
    """F001: Given `Θεσσαλονίκη` (Griechenland, MeteoAlarm-Mitglied) / When
    `fold_ascii` aufgerufen wird / Then ist das Ergebnis `Thessaloniki` --
    nicht die leere Zeichenkette."""
    from utils.ascii_fold import fold_ascii

    assert fold_ascii("Θεσσαλονίκη") == "Thessaloniki", (
        f"Griechischer Ortsname darf nicht verschwinden: "
        f"{fold_ascii('Θεσσαλονίκη')!r}"
    )


def test_fold_ascii_folds_greek_kavala():
    """F001: Given `Καβάλα` / When `fold_ascii` aufgerufen wird / Then ist
    das Ergebnis `Kavala`."""
    from utils.ascii_fold import fold_ascii

    assert fold_ascii("Καβάλα") == "Kavala", (
        f"Griechischer Ortsname darf nicht verschwinden: {fold_ascii('Καβάλα')!r}"
    )


def test_fold_ascii_folds_cyrillic_bulgarian_sofia():
    """F001 (korrigiert, PO-Vorgabe 2026-07-13): Given `София` (Bulgarien,
    MeteoAlarm-Mitglied) / When `fold_ascii` aufgerufen wird / Then ist der
    Ort wiedererkennbar (Praefix `Sof`) -- eine amtliche Umschrift ist NICHT
    das Ziel, nur dass der Name nicht verschwindet und auffindbar bleibt."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("София")
    assert folded.startswith("Sof"), (
        f"Kyrillischer Ortsname muss wiedererkennbar bleiben (Praefix 'Sof'): "
        f"{folded!r}"
    )
    assert folded.isascii()


def test_fold_ascii_folds_cyrillic_bulgarian_plovdiv():
    """F001 (korrigiert): Given `Пловдив` / When `fold_ascii` aufgerufen
    wird / Then enthaelt das Ergebnis `Plovdiv` als wiedererkennbaren
    Teilstring."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Пловдив")
    assert "Plovdiv" in folded, (
        f"Kyrillischer Ortsname muss wiedererkennbar bleiben ('Plovdiv' als "
        f"Teilstring): {folded!r}"
    )
    assert folded.isascii()


def test_fold_ascii_folds_cyrillic_ukrainian_kyiv():
    """F001 (korrigiert): Given `Київ` (ukrainische Schreibweise, Zeichen
    `ї`) / When `fold_ascii` aufgerufen wird / Then bleibt der Ort
    wiedererkennbar (Praefix `Ki`, Endung `v`) -- die generische Map liefert
    `Kiyiv` statt der amtlichen Umschrift `Kyiv`, beides ist auf einer Karte
    auffindbar."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("Київ")
    assert folded.startswith("Ki"), (
        f"Kyrillischer Ortsname muss wiedererkennbar bleiben (Praefix 'Ki'): "
        f"{folded!r}"
    )
    assert folded.endswith("v"), (
        f"Kyrillischer Ortsname muss wiedererkennbar bleiben (Endung 'v'): "
        f"{folded!r}"
    )
    assert folded.isascii()


def test_official_alert_sms_names_greek_location_real_send_path():
    """F001 (CRITICAL) Nutzer-Beweis: Given eine amtliche Warnung betrifft
    `Θεσσαλονίκη` / When die SMS ueber den ECHTEN Versand-Renderer
    (`render_official_alert_sms`) gebaut wird / Then NENNT die SMS den
    transliterierten Ort (`Thessaloniki`) -- vorher lautete die SMS
    `"GZ AMT ORANGE2/3: TH, nur "` (Ortsangabe komplett leer, weil
    `fold_ascii` den griechischen Namen zu `""` gefaltet hat)."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    notices = _compare_notices_for_single_location("Θεσσαλονίκη")
    sms = render_official_alert_sms(notices, sms_prefix="GZ", tz=UTC)

    assert "Thessaloniki" in sms, (
        f"Transliterierter Ortsname fehlt in der SMS -- amtliche Warnung ohne "
        f"Ortsangabe: {sms!r}"
    )
    assert "nur Thessaloniki" in sms, (
        f"SMS traegt weiterhin eine leere Ortsangabe statt 'nur Thessaloniki': "
        f"{sms!r}"
    )
    assert sms.isascii(), f"SMS muss reines ASCII/GSM-7 bleiben: {sms!r}"
    assert len(sms) <= 140, f"SMS ueberschreitet das 140-Zeichen-Limit: {len(sms)}"


def test_official_alert_sms_names_serbian_location_real_send_path():
    """PO-Auftrag 2026-07-13 Nutzer-Beweis (Serbisch, kyrillisches
    Schriftsystem OHNE Serbisch-Eintrag in der ALTEN handgepflegten
    `_CYRILLIC_MAP`, Adversary-Fund Runde 3): Given eine amtliche Warnung
    betrifft `Ђердап` / When die SMS ueber den ECHTEN Versand-Renderer
    (`render_official_alert_sms`) gebaut wird / Then NENNT die SMS den
    transliterierten Ort (`Djerdap`), das Ortsfeld ist NICHT leer und NICHT
    auf `erdap` verstuemmelt."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    notices = _compare_notices_for_single_location("Ђердап")
    sms = render_official_alert_sms(notices, sms_prefix="GZ", tz=UTC)

    assert "Djerdap" in sms, (
        f"Transliterierter serbischer Ortsname fehlt in der SMS -- amtliche "
        f"Warnung ohne (oder verstuemmelte) Ortsangabe: {sms!r}"
    )
    assert "nur Djerdap" in sms, (
        f"SMS traegt keine vollstaendige Ortsangabe 'nur Djerdap': {sms!r}"
    )
    assert "nur erdap" not in sms, (
        f"SMS traegt die verstuemmelte Form 'erdap' statt 'Djerdap': {sms!r}"
    )
    assert sms.isascii(), f"SMS muss reines ASCII/GSM-7 bleiben: {sms!r}"
    assert len(sms) <= 140, f"SMS ueberschreitet das 140-Zeichen-Limit: {len(sms)}"


def test_official_alert_sms_cyrillic_worst_case_length_budget():
    """AC-8 Laengen-Budget-Worst-Case (Auftrag): mehrere kyrillische Orte mit
    dem teuersten Digraphen (`Щ` -> `Shch`, 4 ASCII-Zeichen aus 1
    kyrillischem Zeichen) gleichzeitig in einer gemischten SMS (drei
    unterschiedliche Warnstufen -> jede Warnung traegt ihren eigenen Ort,
    Zweig `render_official_alert_sms` non-uniform). Auch im Worst Case
    bleibt die SMS <=160 Zeichen und rein ASCII -- `_sms_pack_with_fallback`
    droppt notfalls ganze Tokens vom schwaechsten Ende her."""
    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice,
        render_official_alert_sms,
    )
    from services.official_alerts.models import OfficialAlert

    names = ["Щёлково", "Мещёвск", "Иващенково"]
    notices = []
    for name, level in zip(names, [2, 3, 4]):
        alert = OfficialAlert(
            source="vigilance", hazard="thunderstorm", level=level, label="Gewitter",
            valid_from=None, valid_to=None, region_label="Region",
        )
        notices.append(OfficialAlertNotice(
            alert=alert, scope_label=f"nur {name}",
            sms_scope=f"nur{name.replace(' ', '')}",
            affected_chips=[name], free_chips=[], scope_kind="locations",
        ))

    sms = render_official_alert_sms(notices, sms_prefix="GZ", limit=160, tz=UTC)

    assert sms.isascii(), f"SMS ist nicht rein ASCII/GSM-7: {sms!r}"
    assert len(sms) <= 160, f"SMS ueberschreitet 160 Zeichen: {len(sms)} — {sms!r}"


def test_official_alert_sms_mixed_scripts_worst_case_length_budget():
    """PO-Auftrag 2026-07-13: mehrere Orte aus VIER verschiedenen Schriften
    (kyrillisch/russisch, griechisch, maltesisch, kyrillisch/serbisch)
    gleichzeitig in einer gemischten SMS -- genau der Fall, den vorher drei
    getrennte handgepflegte Tabellen (Griechisch/Kyrillisch/Umlaut) NIE
    gemeinsam abdeckten. Auch im Worst Case bleibt die SMS <=160 Zeichen und
    rein ASCII, und alle vier transliterierten Orte sind namentlich
    enthalten."""
    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice,
        render_official_alert_sms,
    )
    from services.official_alerts.models import OfficialAlert

    names = ["Щёлково", "Θεσσαλονίκη", "Ħamrun", "Ђердап"]
    notices = []
    for name, level in zip(names, [2, 3, 4, 3]):
        alert = OfficialAlert(
            source="vigilance", hazard="thunderstorm", level=level, label="Gewitter",
            valid_from=None, valid_to=None, region_label="Region",
        )
        notices.append(OfficialAlertNotice(
            alert=alert, scope_label=f"nur {name}",
            sms_scope=f"nur{name.replace(' ', '')}",
            affected_chips=[name], free_chips=[], scope_kind="locations",
        ))

    sms = render_official_alert_sms(notices, sms_prefix="GZ", limit=160, tz=UTC)

    assert sms.isascii(), f"SMS ist nicht rein ASCII/GSM-7: {sms!r}"
    assert len(sms) <= 160, f"SMS ueberschreitet 160 Zeichen: {len(sms)} — {sms!r}"
    for expected in ("Shchelkovo", "Thessaloniki", "Hamrun", "Djerdap"):
        assert expected in sms, (
            f"Transliterierter Ort {expected!r} fehlt in der Mixed-Script-SMS: "
            f"{sms!r}"
        )


# ---------------------------------------------------------------------------
# Adversary-Finding F001 (Runde 4, CRITICAL) -- `anyascii` deckt NICHT jeden
# Unicode-Buchstaben ab. Arabische Konsonantenschriften (Kategorie `Lo`)
# falten teilweise zu leerem String; der alte `backslashreplace`-"Guard"
# griff erst NACH `anyascii()` und konnte deshalb nie auslösen (leerer
# String ist immer gueltiges ASCII, loest keine UnicodeEncodeError aus).
# ---------------------------------------------------------------------------


def test_fold_ascii_arabic_alif_not_empty():
    """F001 (Runde 4): Given das einzelne Zeichen `ا` (ARABIC LETTER ALEF,
    Unicode-Kategorie `Lo`, faltet bei `anyascii` allein zu leerem String) /
    When `fold_ascii` aufgerufen wird / Then ist das Ergebnis NICHT leer --
    der zeichenweise Guard muss einen sichtbaren Ersatz einsetzen, statt den
    Buchstaben ersatzlos zu loeschen."""
    from utils.ascii_fold import fold_ascii

    folded = fold_ascii("ا")
    assert folded, "Arabischer Buchstabe 'ا' faltet zu leerem String"
    assert folded.isascii()


def test_official_alert_sms_names_arabic_location_real_send_path():
    """F001 (Runde 4) Nutzer-Beweis: Given eine amtliche Warnung betrifft
    den Ort `ا` (Extremfall: ein einzelner arabischer Buchstabe, der bei
    `anyascii` allein zu leerem String faltet) / When die SMS ueber den
    ECHTEN Versand-Renderer (`render_official_alert_sms`) gebaut wird / Then
    ist das Ortsfeld der SMS NICHT leer -- vorher lautete die SMS
    'GZ AMT ORANGE2/3: TH, nur ' (Ortsangabe komplett leer)."""
    from output.renderers.alert.official_alerts import render_official_alert_sms

    notices = _compare_notices_for_single_location("ا")
    sms = render_official_alert_sms(notices, sms_prefix="GZ", tz=UTC)

    assert "nur " in sms, f"SMS traegt kein Scope-Praefix 'nur ': {sms!r}"
    assert "nur " not in sms or not sms.rstrip().endswith("nur"), (
        f"SMS-Ortsfeld ist leer (endet auf blankes 'nur'): {sms!r}"
    )
    scope_part = sms.split("nur ", 1)[1] if "nur " in sms else ""
    assert scope_part.strip(), f"Ortsfeld der SMS ist leer: {sms!r}"
    assert sms.isascii(), f"SMS muss reines ASCII/GSM-7 bleiben: {sms!r}"
    assert len(sms) <= 140, f"SMS ueberschreitet das 140-Zeichen-Limit: {len(sms)}"


# ---------------------------------------------------------------------------
# Adversary-Finding F003 (Runde 4, HIGH) -- NFD-zerlegte Eingabe umgeht die
# Umlaut-Digraph-Map, weil diese nur den precomposed Codepoint matcht.
# ---------------------------------------------------------------------------


def test_fold_ascii_nfd_umlaut_input_still_uses_digraph_map():
    """F003 (Runde 4): Given `München` NFD-zerlegt hereinkommt (Basiszeichen
    'u' + COMBINING DIAERESIS U+0308 statt des precomposed 'ü' = U+00FC,
    plausibel bei Upstream-Feeds/macOS-Werkzeugen) / When `fold_ascii`
    aufgerufen wird / Then ist das Ergebnis weiterhin `Muenchen` (Umlaut-
    Digraph-Map greift), NICHT `Munchen` (Diaerese von `anyascii` stillos
    verworfen, weil die Map den zerlegten Codepoint nicht matchte)."""
    import unicodedata

    from utils.ascii_fold import fold_ascii

    nfd_muenchen = unicodedata.normalize("NFD", "München")
    assert nfd_muenchen != "München", (
        "Testvoraussetzung verletzt: NFD-Normalisierung muss den Codepoint "
        "tatsaechlich zerlegen (sonst testet dieser Fall nichts)"
    )

    result = fold_ascii(nfd_muenchen)
    assert result == "Muenchen", (
        f"NFD-zerlegte Eingabe muss trotzdem zur Umlaut-Digraph-Map falten -- "
        f"erwartet 'Muenchen', erhalten: {result!r}"
    )
    assert result != "Munchen", (
        "fold_ascii hat die NFD-Diaerese stillschweigend verworfen statt zur "
        "'ue'-Digraph-Map zu falten -- fehlende NFC-Normalisierung VOR der "
        "Umlaut-Map"
    )
