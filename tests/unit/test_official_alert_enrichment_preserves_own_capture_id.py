"""Issue #1944, AC-4 (Adversary-Fund F001): die Anreicherung an der
``base.py``-Naht ist REIN ADDITIV -- sie ueberschreibt nie eine Kennung, die
eine Quelle bereits selbst gebunden hat.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md
(Implementation Details, ``base.py``-Naht: "additiv, ueberschreibt nie eine
bereits gesetzte capture_id"; Sonderfall ``massif_closure``)

Bisher war diese Zusicherung unbewacht: der Adversary entfernte die additive
Bedingung (``a if a.capture_id is not None else replace(...)`` -> immer
``replace(...)``) und alle 26 Tests blieben gruen (Finding F001).

Geprueft wird dort, wo die Regel WIRKT -- durch
``get_official_alerts_with_status()`` hindurch, nicht an
``_enrich_with_capture_id`` isoliert.

🔴 EINGEBAUTE POSITIVKONTROLLE: dieselbe Quelle liefert ZWEI Warnungen -- eine
mit eigener Bindung (muss unveraendert bleiben) und eine ohne (muss von der
Naht angereichert werden). Ohne die zweite waere "Kennung unveraendert" auch
die Antwort einer Naht, die an dieser Stelle gar nichts beobachtet hat.

Mock-frei: echte Quelle per strukturellem Subtyping, echte ``httpx.Response``-
Objekte, echte Mitschnitt-Dateien strukturell per ``json.loads`` gelesen,
echte ``collect_capture_ids``-Verschachtelung wie in ``massif_closure``.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx

LAT, LON = 43.314, 5.700

# Eigene Bindung ("massif_closure"-Muster) vs. Beobachtung der aeusseren Naht
SCHLUESSEL_EIGEN = "1944-f001-eigene-bindung"
SCHLUESSEL_NAHT = "1944-f001-naht-sichtbar"


def _kennung_fuer_cache_key(cache_key: str) -> str:
    from app.loader import get_data_root

    verzeichnis = get_data_root() / "debug" / "alert_input" / "official_alert"
    treffer = [
        satz for satz in (json.loads(p.read_text()) for p in sorted(verzeichnis.glob("*.json")))
        if satz.get("payload", {}).get("cache_key") == cache_key
    ]
    assert len(treffer) == 1, (
        f"Erwartet genau EINEN Mitschnitt fuer cache_key={cache_key!r}, "
        f"gefunden {len(treffer)}."
    )
    return treffer[0]["capture_id"]


class _QuelleMitEigenerBindung:
    """Echte Quelle (strukturelles Subtyping, kein Mock) nach dem Muster von
    ``massif_closure``: der erste Abruf laeuft in einem EIGENEN, engen
    Beobachtungs-Kontext und wird sofort an die Warnung gebunden -- die
    aeussere Naht sieht davon nichts. Ein zweiter Abruf laeuft OHNE engen
    Kontext und ist damit die einzige Beobachtung der aeusseren Naht."""

    def __init__(self) -> None:
        self.cache: dict = {}

    @property
    def name(self) -> str:
        return "test-1944-eigene-bindung"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def _abruf(self, cache_key: str) -> None:
        from services.official_alerts import warn_egress

        warn_egress.cached_fetch(
            cache=self.cache, cache_key=cache_key,
            service=self.name, host="eigen.invalid",
            request_fn=lambda: httpx.Response(200, json={"schluessel": cache_key}),
            parse_fn=lambda r: r.json(),
        )

    def fetch(self, lat: float, lon: float):
        from services.official_alerts import warn_egress
        from services.official_alerts.models import OfficialAlert

        eigene: list[str] = []
        with warn_egress.collect_capture_ids(eigene):
            self._abruf(SCHLUESSEL_EIGEN)
        assert len(set(eigene)) == 1, f"Eigene Bindung erwartet genau eine Kennung: {eigene!r}"
        eigene_kennung = eigene[0]

        # Ausserhalb des engen Kontexts -> die aeussere Naht beobachtet genau
        # DIESE eine, andere Kennung.
        self._abruf(SCHLUESSEL_NAHT)

        jetzt = datetime.now(timezone.utc)
        # Zwei verschiedene Gefahrenarten -- sonst kollabiert die Dubletten-
        # Regel in ``base.py`` (Schluessel hazard/valid_from/valid_to) die
        # beiden Warnungen zu einer.
        vorlage = dict(
            source="test-1944", level=3,
            valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
        )
        return [
            OfficialAlert(
                hazard="wind", label="Sturmwarnung (eigene Bindung)",
                region_label="Selbst gebunden", capture_id=eigene_kennung, **vorlage,
            ),
            OfficialAlert(
                hazard="rain", label="Regenwarnung (ohne Bindung)",
                region_label="Ohne Bindung", **vorlage,
            ),
        ]


def test_ac4_naht_ueberschreibt_eine_selbst_gebundene_kennung_nicht(monkeypatch, tmp_path):
    """AC-4: GIVEN eine Quelle bindet die Kennung ihres eigenen Abrufs bereits
    selbst an eine Warnung (wie ``massif_closure``) und die aeussere Naht
    beobachtet dabei GENAU EINE andere Kennung, WHEN
    ``get_official_alerts_with_status()`` anreichert, THEN bleibt die selbst
    gebundene Kennung unveraendert -- angereichert wird nur, was noch keine
    eigene traegt."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import warn_egress
    from services.official_alerts.base import get_official_alerts_with_status

    monkeypatch.setattr(
        warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "warn_service_calls.jsonl"
    )
    sicherung = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        oa_base._REGISTERED_SOURCES.append(_QuelleMitEigenerBindung())
        alerts, unavailable = get_official_alerts_with_status(LAT, LON)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sicherung)

    assert unavailable is False and len(alerts) == 2, (
        f"Voraussetzung: die Quelle liefert zwei Warnungen, war {alerts!r}"
    )
    nach_label = {a.label: a for a in alerts}
    eigene_kennung = _kennung_fuer_cache_key(SCHLUESSEL_EIGEN)
    naht_kennung = _kennung_fuer_cache_key(SCHLUESSEL_NAHT)
    assert eigene_kennung != naht_kennung, (
        "Voraussetzung der Messung: die beiden Abrufe muessen unterscheidbare "
        "Kennungen tragen."
    )

    # Positivkontrolle: die Naht hat an dieser Stelle GENAU EINE Kennung
    # beobachtet und reichert damit auch wirklich an.
    ohne = nach_label["Regenwarnung (ohne Bindung)"]
    assert ohne.capture_id == naht_kennung, (
        f"Positivkontrolle gescheitert: die Naht muss eine Warnung OHNE eigene "
        f"Kennung mit der beobachteten anreichern -- {ohne.capture_id!r} != "
        f"{naht_kennung!r}. Ohne diesen Nachweis waere die Zusicherung unten "
        f"trivial erfuellt."
    )

    gebunden = nach_label["Sturmwarnung (eigene Bindung)"]
    assert gebunden.capture_id == eigene_kennung, (
        f"Die selbst gebundene Kennung MUSS die Anreicherung ueberleben: "
        f"war={gebunden.capture_id!r}, eigene={eigene_kennung!r}, "
        f"von der Naht beobachtete={naht_kennung!r}"
    )
    assert gebunden.capture_id != naht_kennung, (
        "Die Naht darf eine bereits gesetzte Kennung nie durch die von ihr "
        "beobachtete ersetzen -- die Warnung zeigte sonst auf den falschen "
        "Roh-Datensatz."
    )
