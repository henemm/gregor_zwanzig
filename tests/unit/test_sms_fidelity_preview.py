"""TDD-RED: Briefing-SMS-Fidelity über Backend-Feed (Issue #923).

Spec: docs/specs/modules/fix_923_sms_fidelity_backend.md
ADR: ADR-0011 (ein einziger Backend-Renderer, kein zweiter im Frontend)

Kein Mock. Tests laufen gegen den echten FastAPI-Router (isolierte Test-App,
Muster aus tests/integration/test_issue_918_alert_preview_4ch.py /
tests/tdd/test_issue_464_compare_email_preview.py) bzw. rufen die neuen
Python-Funktionen direkt auf.

RED heute — alle Tests schlagen fehl, weil:
  - `POST /api/_validator/sms-fidelity-preview` noch nicht existiert (404).
  - `services.validator_render_service.render_sms_fidelity_preview()`,
    `.SMS_FIDELITY_SAMPLE_FORECAST`, `.build_sms_fidelity_specs()` noch nicht
    existieren (ImportError).
  - `output.tokens.render.render_line_with_survivors()` noch nicht existiert
    (ImportError).

Test-Kontrakt (von dieser RED-Phase festgelegt, Implementierung folgt in
/50-implement):
  - `render_sms_fidelity_preview(metric_ids: list[str]) -> dict` mit Keys
    line/char_count/max_length/carried_ids. Nutzt intern eine feste
    `SMS_FIDELITY_SAMPLE_FORECAST` (NormalizedForecast) und
    `build_sms_fidelity_specs(metric_ids) -> list[MetricSpec]` (disabled_specs
    nach dem Muster trip_report.py:283-307), ruft `build_token_line()` +
    `render_line_with_survivors()` — dieselben Funktionen wie der Versandpfad
    — direkt auf.
  - `render_line_with_survivors(line, max_length) -> tuple[str, set[str]]`
    (Nachbarfunktion zu `render_line()`, dieselben privaten Kürzungs-Helfer,
    liefert zusätzlich die ueberlebenden Token-Symbole).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from output.tokens.builder import build_token_line
from output.tokens.render import render_line

# Alle metric_ids, die per SMS_SYMBOL_BY_METRIC / SMS_MULTI_SYMBOLS_BY_METRIC
# (output.renderers.sms_trip) ein eigenes SMS-Token-Symbol tragen.
# Issue #1484: "N" (Nacht-Tiefsttemperatur) hängt jetzt an der eigenen
# metric_id "temperature_night", nicht mehr an "temperature".
# Issue #1660 Scheibe A: dieselbe Trennung jetzt auch auf der gefuehlten
# Seite -- "FN" haengt an der eigenen metric_id "wind_chill_night".
ALL_SMS_METRIC_IDS = [
    "temperature", "temperature_night", "wind_chill", "wind_chill_night",
    "precipitation", "rain_probability", "wind", "gust", "thunder",
    "snow_depth", "snowfall_limit", "fresh_snow",
]

# metric_id -> SMS-Symbol(e), die bei Auswahl im gerenderten Text vorkommen
# müssen. Gespiegelt aus output.renderers.sms_trip.SMS_SYMBOL_BY_METRIC /
# SMS_MULTI_SYMBOLS_BY_METRIC (§624/§1410/§1435/§1484/§1660). Bewusst hier
# dupliziert (nicht importiert), damit der Test unabhängig von der internen
# Ableitung bleibt und wirklich das SICHTBARE Symbol im Rendertext prüft.
METRIC_TO_SYMBOLS = {
    "temperature": ("K", "D"),
    "temperature_night": ("N",),
    "wind_chill": ("FK", "FD", "WC"),
    "wind_chill_night": ("FN",),
    "precipitation": ("R",),
    "rain_probability": ("PR",),
    "wind": ("W",),
    "gust": ("G",),
    "thunder": ("TH:", "TH+:"),
    "snow_depth": ("SD",),
    "snowfall_limit": ("SL",),
    "fresh_snow": ("NS24+",),
}

# Reine Tabellen-Metrik ohne jedes SMS-Token-Symbol (nicht Teil von
# SMS_SYMBOL_BY_METRIC/SMS_MULTI_SYMBOLS_BY_METRIC) — AC-4-Fixture.
NO_SMS_TOKEN_METRIC_ID = "cloud_total"


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


def _independent_line_and_survivors(metric_ids: list[str]) -> tuple[str, set[str]]:
    """Baut Erwartungswert unabhängig aus denselben Bausteinen, die die neue
    Funktion intern nutzen soll: dieselbe feste Beispiel-Vorhersage
    (`SMS_FIDELITY_SAMPLE_FORECAST`) + dieselbe Spec-Ableitung
    (`build_sms_fidelity_specs`), aber mit einem eigenständigen
    `build_token_line()`/`render_line_with_survivors()`-Aufruf — beweist,
    dass der Endpoint keine eigene Kürzungslogik simuliert (AC-1/AC-2)."""
    from services.validator_render_service import (
        SMS_FIDELITY_SAMPLE_FORECAST,
        build_sms_fidelity_specs,
    )
    from output.tokens.render import render_line_with_survivors

    specs = build_sms_fidelity_specs(metric_ids)
    token_line = build_token_line(
        SMS_FIDELITY_SAMPLE_FORECAST, specs,
        report_type="evening", stage_name="Etappe",
    )
    return render_line_with_survivors(token_line, 160)


# ─── AC-1 ────────────────────────────────────────────────────────────────────

class TestAC1_NoTruncationByteIdentical:
    """AC-1: line ist bytegleich zum direkten Aufruf derselben Funktionen,
    wenn keine Kürzung nötig ist."""

    def test_line_matches_direct_pipeline_call_no_truncation(self, client):
        metric_ids = ["temperature"]
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": metric_ids},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()

        expected_line, _survivors = _independent_line_and_survivors(metric_ids)
        assert data["line"] == expected_line, (
            f"AC-1: Endpoint-line {data['line']!r} weicht vom direkten "
            f"render_line(build_token_line(...))-Aufruf {expected_line!r} ab — "
            "der Endpoint darf keine eigene Kürzungs-/Renderlogik simulieren."
        )


# ─── AC-2 ────────────────────────────────────────────────────────────────────

class TestAC2_TruncationByteIdenticalAndCarriedIdsCorrect:
    """AC-2: bei erzwungener Kürzung bleibt line bytegleich, und carried_ids
    entspricht genau den nach §6-Kürzung ueberlebenden Symbolen."""

    def test_line_matches_direct_pipeline_call_with_truncation(self, client):
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ALL_SMS_METRIC_IDS},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()

        expected_line, survivor_symbols = _independent_line_and_survivors(
            ALL_SMS_METRIC_IDS
        )
        # Vorbedingung: dieser Testfall MUSS tatsächlich kürzen (sonst prüft
        # er die falsche Verzweigung, s. CLAUDE.md "Mutations-Gegenprobe" /
        # NORMALFALL-vs-Warnstufen-Regel).
        assert len(expected_line) <= 160, (
            "AC-2-Fixture erzeugt keine kürzungspflichtige Zeile "
            f"({len(expected_line)} Zeichen) — Beispiel-Vorhersage in "
            "SMS_FIDELITY_SAMPLE_FORECAST muss so gewählt sein, dass ALLE "
            "SMS-fähigen Metriken zusammen die 160-Zeichen-Grenze überschreiten."
        )
        assert data["line"] == expected_line, (
            f"AC-2: Endpoint-line {data['line']!r} weicht vom direkten "
            f"Pipeline-Aufruf {expected_line!r} ab."
        )

    def test_carried_ids_match_symbols_surviving_truncation(self, client):
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ALL_SMS_METRIC_IDS},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()
        line = data["line"]
        carried_ids = set(data["carried_ids"])

        for metric_id in ALL_SMS_METRIC_IDS:
            symbols = METRIC_TO_SYMBOLS[metric_id]
            symbol_present = any(sym in line for sym in symbols)
            if metric_id in carried_ids:
                assert symbol_present, (
                    f"AC-2: '{metric_id}' steht in carried_ids, aber keines "
                    f"seiner Symbole {symbols} kommt in line vor: {line!r}"
                )
            else:
                assert not symbol_present, (
                    f"AC-2: '{metric_id}' fehlt in carried_ids, aber eines "
                    f"seiner Symbole {symbols} kommt trotzdem in line vor "
                    f"(Kürzung nicht korrekt gespiegelt): {line!r}"
                )

    def test_truncation_actually_removes_content(self, client):
        """Gegenprobe zur AC-2-Vorbedingung: die volle (ungekürzte) Token-Zeile
        muss über 160 Zeichen liegen, und die Antwort muss kürzer als diese
        volle Zeile sein — sonst wurde gar nichts gekürzt und die anderen
        AC-2-Tests prüften den falschen Fall.

        Korrigiert gegenüber der RED-Fassung (die forderte, dass mindestens
        eine ganze metric_id komplett aus carried_ids verschwindet): §6
        DROP_ORDER entfernt zuerst einzelne Symbole (hier: WC), nicht
        zwangsläufig eine ganze mehrsymbolige Metrik wie wind_chill
        (FN/FK/FD überleben weiterhin) — das ist korrektes Verhalten der
        carried_ids-Ableitung, kein Fehler. Der ursprüngliche Test verlangte
        mehr, als AC-2 tatsächlich zusichert."""
        from services.validator_render_service import (
            SMS_FIDELITY_SAMPLE_FORECAST,
            build_sms_fidelity_specs,
        )

        specs = build_sms_fidelity_specs(ALL_SMS_METRIC_IDS)
        token_line = build_token_line(
            SMS_FIDELITY_SAMPLE_FORECAST, specs,
            report_type="evening", stage_name="Etappe",
        )
        full_raw = (
            f"{token_line.stage_name}: "
            + " ".join(t.render() for t in token_line.tokens)
        )
        assert len(full_raw) > 160, (
            f"AC-2-Fixture erzeugt keine kürzungspflichtige volle Zeile "
            f"({len(full_raw)} Zeichen): {full_raw!r}"
        )

        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ALL_SMS_METRIC_IDS},
        )
        assert resp.status_code == 200
        line = resp.json()["line"]
        assert len(line) < len(full_raw), (
            f"AC-2: die Antwort ({len(line)} Zeichen) ist nicht kürzer als "
            f"die volle, ungekürzte Zeile ({len(full_raw)} Zeichen) — keine "
            "Kürzung fand statt."
        )


# ─── AC-3 ────────────────────────────────────────────────────────────────────

class TestAC3_StatelessNoUserId:
    """AC-3: kein user_id-Parameter, kein existierender Trip nötig — 200 +
    valide Response-Shape (zustandslos wie alert-preview/compare-email-preview)."""

    def test_no_user_id_param_returns_200(self, client):
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ["temperature", "wind"]},
        )
        assert resp.status_code == 200, (
            f"AC-3: erwartet 200 ohne user_id-Query-Param, bekam "
            f"{resp.status_code}: {resp.text[:300]}"
        )

    def test_response_has_valid_shape(self, client):
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ["temperature", "wind"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in ("line", "char_count", "max_length", "carried_ids"):
            assert field in data, f"AC-3: Feld '{field}' fehlt: {list(data)}"
        assert isinstance(data["line"], str)
        assert isinstance(data["char_count"], int)
        assert isinstance(data["max_length"], int)
        assert isinstance(data["carried_ids"], list)

    def test_empty_selection_still_returns_200(self, client):
        """Kein Trip, keine Metrik — der Endpoint liest keine Nutzerdaten."""
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": []},
        )
        assert resp.status_code == 200, (
            f"AC-3: leere Auswahl muss 200 liefern (zustandslos), bekam "
            f"{resp.status_code}: {resp.text[:300]}"
        )


# ─── AC-4 ────────────────────────────────────────────────────────────────────

class TestAC4_MetricWithoutSmsCodeExcluded:
    """AC-4: eine reine Tabellen-Metrik ohne SMS-Token-Symbol fehlt in
    carried_ids, obwohl sie angefragt wurde."""

    def test_metric_without_token_symbol_missing_from_carried_ids(self, client):
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ["temperature", NO_SMS_TOKEN_METRIC_ID]},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        carried_ids = resp.json()["carried_ids"]
        assert NO_SMS_TOKEN_METRIC_ID not in carried_ids, (
            f"AC-4: '{NO_SMS_TOKEN_METRIC_ID}' hat kein SMS-Token-Symbol und "
            f"darf nicht in carried_ids stehen: {carried_ids}"
        )
        assert "temperature" in carried_ids, (
            "AC-4-Kontrollfixture: 'temperature' sollte bei nur zwei "
            f"angefragten Metriken ohne Kürzungsdruck ueberleben: {carried_ids}"
        )


# ─── AC-5 ────────────────────────────────────────────────────────────────────

class TestAC5_MaxLengthIs160NotOldFrontendValue:
    """AC-5: max_length stammt vom Server und ist 160 (dokumentierter Wert
    aus sms_format.md), NICHT die alte hartcodierte Frontend-Konstante 140."""

    def test_max_length_is_160(self, client):
        resp = client.post(
            "/api/_validator/sms-fidelity-preview",
            json={"metric_ids": ["temperature"]},
        )
        assert resp.status_code == 200
        max_length = resp.json()["max_length"]
        assert max_length == 160, (
            f"AC-5: max_length muss 160 sein (sms_format.md, dokumentiertes "
            f"Limit), bekam {max_length} — 140 ist die überholte "
            "Frontend-Simulationskonstante."
        )


# ─── AC-9 (Regression render_line()) ───────────────────────────────────────

class TestAC9_RenderLineUnchangedByAdditiveFunction:
    """AC-9: die neue additive Funktion in output.tokens.render ändert nichts
    am bestehenden Verhalten von render_line() — Byte-Vergleich für einen
    TATSÄCHLICH kürzungspflichtigen Fall gegen den vor dieser Änderung
    gemessenen Wert.

    Adversary-Finding F001 (2026-08-06, AMBIGUOUS-Runde): die ursprüngliche
    Fixture (identisch zu tests/unit/test_renderers_sms.py::_long_token_line)
    hat eine RAW-Zeilenlänge von nur 82 Zeichen — weit unter dem 160-Zeichen-
    Limit. render_line() nimmt dabei den `if len(full) <= max_length: return
    full`-Kurzschluss und ruft `_truncate()` nie auf; eine Mutation
    ausschließlich am Kürzungs-Rückgabepfad blieb dadurch unentdeckt
    (Mutationsprobe 2 im Adversary-Dialog). Diese Klasse nutzt jetzt
    SMS_FIDELITY_SAMPLE_FORECAST + ALL_SMS_METRIC_IDS (bereits an anderer
    Stelle in AC-2 verwendet, RAW-Länge nachgemessen 161 Zeichen > 160) —
    dieselbe Vorbedingungs-Assertion wie bei AC-2 stellt sicher, dass der
    Kürzungszweig auch künftig tatsächlich durchlaufen wird."""

    def _truncating_line(self):
        from services.validator_render_service import (
            SMS_FIDELITY_SAMPLE_FORECAST,
            build_sms_fidelity_specs,
        )

        specs = build_sms_fidelity_specs(ALL_SMS_METRIC_IDS)
        return build_token_line(
            SMS_FIDELITY_SAMPLE_FORECAST, specs,
            report_type="evening", stage_name="Etappe",
        )

    def test_render_line_output_byte_identical_to_pre_change_baseline(self):
        # Vorbedingung wie bei AC-2: die Fixture muss tatsächlich kürzen,
        # sonst prüft dieser Test den falschen (trivialen) Zweig — genau der
        # Fehler, der zu Finding F001 führte.
        token_line_check = self._truncating_line()
        full_raw = (
            f"{token_line_check.stage_name}: "
            + " ".join(t.render() for t in token_line_check.tokens)
        )
        assert len(full_raw) > 160, (
            f"AC-9-Fixture erzeugt keine kürzungspflichtige volle Zeile "
            f"({len(full_raw)} Zeichen): {full_raw!r}"
        )

        # Golden-Wert gemessen VOR dieser Erweiterung (2026-08-06),
        # unverändertes render_line() auf einer TATSÄCHLICH kürzenden Zeile.
        # Issue #1824 (A): nachgezogen — die Temperatur-Paare stehen jetzt als
        # Bereichs-Token ('D-12/28'/'FD-18/24'), und die drei Schnee-Größen der
        # Beispiel-Vorhersage tragen je eine Stelle mehr, damit die Zeile
        # weiterhin über 160 Zeichen liegt (s. Kommentar an
        # SMS_FIDELITY_SAMPLE_FORECAST). Die Zusicherung selbst ist unverändert:
        # render_line() darf sich durch die additive Nachbarfunktion nicht ändern.
        baseline = (
            "Etappe: N-15 D-12/28 FN-21 FD-18/24 R245.0@6(845.0@14) "
            "PR25%@7(98%@14) W850@6(1420@16) G1200@6(2080@16) TH:L@8(H@12) "
            "TH+:M@10 SD245000 NS24+185000 SL980000"
        )
        line = self._truncating_line()
        out = render_line(line, 160)
        assert out == baseline, (
            f"AC-9: render_line() liefert nach der Änderung ein anderes "
            f"Ergebnis als vor der Änderung.\nVorher:  {baseline!r}\n"
            f"Nachher: {out!r}"
        )
        assert len(out) <= 160, f"AC-9: gekürzte Zeile überschreitet 160 Zeichen: {len(out)}"

    def test_new_survivor_function_agrees_with_render_line_on_same_input(self):
        """Die neue Funktion darf render_line() nicht duplizieren mit
        abweichendem Ergebnis — beide müssen für dasselbe Token-Line-Objekt
        denselben Zeichenkette liefern, AUCH im tatsächlichen Kürzungsfall."""
        from output.tokens.render import render_line_with_survivors

        line_a = self._truncating_line()
        expected = render_line(line_a, 160)

        line_b = self._truncating_line()
        out, survivors = render_line_with_survivors(line_b, 160)
        assert out == expected, (
            f"AC-9: render_line_with_survivors()-Text {out!r} weicht von "
            f"render_line() {expected!r} für identischen Input ab."
        )
        assert isinstance(survivors, set)
        assert len(survivors) > 0
