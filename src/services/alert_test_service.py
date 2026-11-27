"""Test-Alarm: Beispiel-Alarm mit echten Werten an alle Alarm-Kanaele (Issue #3441).

Spec: docs/specs/modules/feat_3441_test_alarm.md

Baut je aktiver Alarm-Regel (Trip) bzw. aktiver Alarm-Metrik (Ortsvergleich)
eine Beispiel-Aenderung, die der Renderer als „ueber" der Schwelle beurteilt
(#3462, docs/specs/modules/fix_3462_testalarm_beispielwerte.md): Richtung aus
dem Katalog, Betrag 1.2 x |Schwelle|, Gewitter mindestens „maessig", Prozent
hoechstens 100, je angezeigter Bezeichnung hoechstens eine Aenderung. Sie
geht ueber den bestehenden Alarmweg (``send_deviation_alert`` bzw.
``send_multi_location_deviation_alert``) mit ``test=True`` hinaus. Echte Segmente
bzw. Orte und die echte Stundenreihe kommen aus ``alert_preview_hours``.

Kanalmenge = ``effective_alert_channels`` geschnitten mit der Zustellbarkeit.
Radar-Schalter, stille Stunden, Sperrzeit und Tageslimit gelten nicht: der
Test prueft den Kanal. Der Baustein schreibt keinen Alarm-Zustand (kein
Anker, keine Sperrzeit, kein Protokoll); das SMS-Tageskontingent und
``manueller_abruf`` zaehlen wie beim Handversand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import Settings
from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity, ChangeSeverity, WeatherChange

_KANAELE = ("email", "telegram", "sms", "premium_sms")
_SCHWERE = {
    AlertSeverity.INFO.value: ChangeSeverity.MINOR,
    AlertSeverity.WARNING.value: ChangeSeverity.MODERATE,
    AlertSeverity.CRITICAL.value: ChangeSeverity.MAJOR,
}
#: Rueckfall ohne aktive Regel bzw. Metrik: Boeen mit der Standardschwelle
#: des Alarm-Editors (``METRIC_DEFAULTS.wind_gust``).
_RUECKFALL = AlertRule(
    id="test-alarm-rueckfall", kind=AlertRuleKind.ABSOLUTE, metric=AlertMetric.WIND_GUST,
    threshold=50.0, severity=AlertSeverity.WARNING, enabled=True,
)


class TestAlarmAbgelehnt(Exception):
    """Test-Alarm ohne Versand; ``code`` stammt aus ``send_outcomes``."""

    __test__ = False  # kein pytest-Testfall

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class TestAlarmErgebnis:
    """Kanalergebnis: gesendet, uebersprungen und fehlgeschlagen (Kanal -> Grund-Schluessel)."""

    __test__ = False

    sent: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)


def _feld(metric: AlertMetric) -> str | None:
    """Summary-Feld der Regel (Delta-Metrik: erstes Feld, wie die Vorschau)."""
    from services.alert_preset import ONSET_METRICS
    from services.weather_change_detection import (
        _ALERT_DELTA_METRIC_TO_FIELDS, _ALERT_METRIC_TO_SUMMARY_FIELD,
    )

    if metric.value in ONSET_METRICS:
        return None  # Zeitpunkt-Felder taugen nicht fuer Schwelle x 1.2
    delta = _ALERT_DELTA_METRIC_TO_FIELDS.get(metric)
    return delta[0] if delta else _ALERT_METRIC_TO_SUMMARY_FIELD.get(metric)


def _faellt(feld: str) -> bool:
    """Richtung aus dem Katalog: ein Kandidat mit cmp "unter" ⇒ fallend (#3462)."""
    from app.metric_catalog import _METRICS

    return any(m.cmp == "unter" for m in _METRICS if feld in m.summary_fields.values())


def _werte(regel: AlertRule, feld: str, richtung: str) -> tuple[float, float]:
    """(alt, neu) mit |neu - alt| = 1.2·|S|, damit der Renderer „über" urteilt (#3462)."""
    import math

    from app.metric_catalog import get_metric
    from output.renderers.alert.project import _resolve_metric_id

    schwelle = float(regel.threshold)
    betrag = 1.2 * abs(schwelle)
    if feld == "thunder_level_max":
        return 0.0, float(min(3, max(2, math.ceil(1.2 * schwelle))))
    if richtung == "decrease":
        neu = 0.8 * schwelle
        alt = neu + betrag
    else:
        alt = 0.0 if AlertRuleKind(regel.kind) == AlertRuleKind.DELTA else 0.8 * schwelle
        neu = alt + betrag
    if get_metric(_resolve_metric_id(feld, richtung)).unit == "%":
        neu = min(100.0, neu)
        alt = max(0.0, neu - betrag)
    return alt, neu


def _beispiel(regel: AlertRule, segment_id: str) -> WeatherChange | None:
    try:
        feld = _feld(AlertMetric(regel.metric))
    except ValueError:
        return None
    if feld is None:
        return None
    richtung = "decrease" if _faellt(feld) else "increase"
    alt, neu = _werte(regel, feld, richtung)
    schwere = getattr(regel.severity, "value", regel.severity)
    return WeatherChange(
        metric=feld, old_value=alt, new_value=neu, delta=neu - alt, threshold=float(regel.threshold),
        severity=_SCHWERE.get(schwere, ChangeSeverity.MODERATE),
        direction=richtung, segment_id=segment_id,
    )


def _je_bezeichnung_einmal(changes: list[WeatherChange]) -> list[WeatherChange]:
    """Je angezeigter Alarm-Bezeichnung höchstens eine Änderung, erste gewinnt (#3462)."""
    from app.metric_catalog import get_alert_label
    from output.renderers.alert.project import _resolve_metric_id

    gesehen: set[str] = set()
    ergebnis = []
    for c in changes:
        label = get_alert_label(_resolve_metric_id(c.metric, c.direction), "de")
        if label not in gesehen:
            gesehen.add(label)
            ergebnis.append(c)
    return ergebnis


def _vergleich_regeln(preset: dict) -> list[AlertRule]:
    """Aktive Alarm-Metriken des Vergleichs mit ihrer Standardschwelle --
    dieselbe Ableitung wie ``CompareAlertService._build_eval_config``."""
    from services.alert_preset import expand_per_metric_levels
    from services.compare_alert import _STANDARD_METRIC_LEVELS, CompareAlertService

    levels = (preset.get("display_config") or {}).get("metric_alert_levels") or _STANDARD_METRIC_LEVELS
    dc = CompareAlertService._display_config_from_active_metrics(None, preset)
    return expand_per_metric_levels(levels, display_config=dc, supplement_missing_levels=True)


def _gewuenschte_kanaele(subscription) -> set[str]:
    """Kanalmenge VOR den Tarif-Gates (fuer die Meldung „nicht im Tarif")."""
    from services.alert_channels import _compare_channel_inputs, _trip_channel_inputs

    adapter = _compare_channel_inputs if isinstance(subscription, dict) else _trip_channel_inputs
    override, inherited, _regeln = adapter(subscription)
    if override is not None:
        return {ch for ch in _KANAELE if override.get(ch)}
    return set(inherited)


def _auswertung(result, skipped: dict[str, str]) -> TestAlarmErgebnis:
    """``NotificationResult`` -> Kanalergebnis. Eine bewusste Sperre (Code)
    ist uebersprungen, ein Transportfehler fehlgeschlagen."""
    from services.sms_daily_limit import REASON_CODE

    codes = result.blocked_reason_codes
    for ch, code in codes.items():
        skipped[ch] = "kontingent" if code == REASON_CODE else "gesperrt"
    failed = {ch: "transport" for ch in result.failed_channels if ch not in codes}
    sent = [ch for ch in result.sent_channels if ch not in failed and ch not in codes]
    return TestAlarmErgebnis(sent=sent, skipped=skipped, failed=failed)


class AlertTestService:
    """Test-Alarm EINES Nutzers fuer Trip (``app.trip.Trip``) und Ortsvergleich (Rohdict)."""

    __test__ = False

    def __init__(self, user_id: str, settings: Settings | None = None) -> None:
        if not user_id:
            raise ValueError("AlertTestService braucht eine echte user_id (#3441)")
        self._user_id = user_id
        self._settings = settings or Settings().with_user_profile(user_id)

    def beispiel_aenderungen(self, subscription, segment_id: str = "") -> list[WeatherChange]:
        """Je aktiver Regel bzw. Alarm-Metrik eine Beispiel-Aenderung; keine ⇒ Rueckfall."""
        if isinstance(subscription, dict):
            regeln = _vergleich_regeln(subscription)
        else:
            regeln = [r for r in subscription.alert_rules or [] if r.enabled]
        changes = [c for c in (_beispiel(r, segment_id) for r in regeln) if c is not None]
        return _je_bezeichnung_einmal(changes) or [_beispiel(_RUECKFALL, segment_id)]

    def kanalmenge(self, subscription) -> tuple[set[str], dict[str, str]]:
        """(bedienbare Alarm-Kanaele, uebersprungene Kanaele -> Grund-Schluessel)."""
        from services.alert_channels import effective_alert_channels

        s = self._settings
        effektiv = effective_alert_channels(subscription, s, self._user_id)
        skipped = {ch: "tarif" for ch in _gewuenschte_kanaele(subscription) - effektiv}
        bereit = {"email": s.can_send_email, "telegram": s.can_send_telegram, "sms": s.can_send_sms}
        for ch in effektiv:
            if ch in bereit and not bereit[ch]():
                skipped[ch] = "nicht_bedienbar"
        return effektiv - set(skipped), skipped

    def senden(self, subscription) -> TestAlarmErgebnis:
        """Beispiel-Alarm an die bedienbaren Alarm-Kanaele; ``TestAlarmAbgelehnt`` ohne Versand."""
        from services.forecast_budget import MANUAL, ForecastBudgetGate, manueller_abruf
        from services.manuelles_kontingent import schaetzung_trip, schaetzung_vergleich

        vergleich = isinstance(subscription, dict)
        ziel = self._orte(subscription) if vergleich else self._segmente(subscription)
        kanaele, skipped = self.kanalmenge(subscription)
        if not kanaele:
            raise TestAlarmAbgelehnt("keine_alarm_kanaele")
        schaetzung = schaetzung_vergleich(len(ziel)) if vergleich else schaetzung_trip(subscription)
        with manueller_abruf(self._user_id, schaetzung) as kontingent:
            if not ForecastBudgetGate(self._user_id).reserve(MANUAL, 1):
                raise TestAlarmAbgelehnt("kontingent_erschoepft")
            senden = self._vergleich_senden if vergleich else self._trip_senden
            result = senden(subscription, ziel, kanaele, kontingent)
        return _auswertung(result, skipped)

    def _notification_service(self):
        from services.notification_service import NotificationService

        return NotificationService(self._settings, self._user_id)

    def _segmente(self, trip) -> list:
        """Echte Segmente des Bezugstags (heute, sonst naechste/letzte Etappe)."""
        from services.trip_day import preview_reference_date
        from services.trip_segments import convert_trip_to_segments

        bezugstag = preview_reference_date(trip, datetime.now(timezone.utc))
        segmente = convert_trip_to_segments(trip, bezugstag) if bezugstag else []
        if not segmente:
            raise TestAlarmAbgelehnt("trip_ohne_segmente")
        return segmente

    def _orte(self, preset: dict) -> list:
        """Echte, aufloesbare Orte des Vergleichs in Preset-Reihenfolge."""
        from app.loader import load_all_locations

        alle = {loc.id: loc for loc in load_all_locations(user_id=self._user_id)}
        orte = [alle[lid] for lid in preset.get("location_ids") or [] if lid in alle]
        if not orte:
            raise TestAlarmAbgelehnt("vergleich_ohne_orte")
        return orte

    def _trip_senden(self, trip, segmente: list, kanaele: set[str], kontingent):
        from services.alert_preview_hours import trip_preview_series
        from services.trip_alert import _trip_telegram_style
        from services.validator_render_service import _preview_segment

        changes = self.beispiel_aenderungen(trip, str(segmente[0].segment_id))
        anker, frisch = trip_preview_series(trip, user_id=self._user_id, now_utc=datetime.now(timezone.utc))
        if kontingent.abgelehnt:
            raise TestAlarmAbgelehnt("kontingent_erschoepft")
        # Ohne Stundenreihe: die echten Segmente ohne Stundenzeilen (nie leer).
        wetter = frisch or [_preview_segment(s) for s in segmente]
        return self._notification_service().send_deviation_alert(
            trip, wetter, changes, kanaele, telegram_style=_trip_telegram_style(trip),
            anchor_weather=anker if frisch else None, test=True,
        )

    def _vergleich_senden(self, preset: dict, orte: list, kanaele: set[str], kontingent):
        from services.alert_preview_hours import compare_preview_point, preview_deadline
        from services.compare_alert import CompareAlertService
        from services.compare_alert_channels import effective_compare_telegram_style

        changes = self.beispiel_aenderungen(preset)
        frist = preview_deadline()  # EIN Budget fuer alle Orte
        entities, anker = [], {}
        for loc in orte:
            frisch, alt = compare_preview_point(preset, preset.get("id", ""), loc,
                                                user_id=self._user_id, deadline=frist)
            entities.append((loc.name, [frisch if frisch is not None else loc], changes))
            if alt is not None:
                anker[loc.name] = alt
        if kontingent.abgelehnt:
            raise TestAlarmAbgelehnt("kontingent_erschoepft")
        positionen = CompareAlertService._location_positions(
            list(preset.get("location_ids") or []), {loc.id: loc for loc in orte},
        )
        return self._notification_service().send_multi_location_deviation_alert(
            entities, kanaele, location_positions=positionen,
            telegram_style=effective_compare_telegram_style(preset),
            anchor_points=anker, preset=preset, test=True,
        )
