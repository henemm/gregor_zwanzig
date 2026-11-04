#!/usr/bin/env python3
"""Migration Issue #2792 S1b: Bestandsdaten auf die Profil-Ampel (ADR-0106).

Spec docs/specs/modules/feat_2792_s1_profil_ampel.md §4 (AC-8..AC-12, AC-17).
Je Nutzer ``<root>/<uid>/briefings/*.json`` (Trip und Vergleich): Vorlage aus
``preset_name`` bzw. ``profil`` (``app.ampel.template_id_for``) nach
``display_config.ampel.template``; ``corridors`` mit ``mark`` (Rueckfall
``ideal_ranges``) -> gruenes Fenster mit Klemm-Regel; ``horizons`` -> alle Tage;
CAPE-Auswahl -> Gewitter aktiv. Nur berichtet: Δ-Bereiche, ``sms_threshold``
(E1), eigene Vorlagen. Unangetastet: Alarmfelder (S2). Vorhandene Ampel-Teile
nie ueberschrieben; unveraenderte Dateien nicht geschrieben. Zweiphasig (erst
planen, dann je Nutzer tar.gz, dann schreiben), Read-Modify-Write (#102).
Vorbild ``scripts/migrate_1231_corridors.py``.

Usage: python3 scripts/migrate_2792_profil_ampel.py --root <data/users> [--backup-dir <p>] [--execute]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.ampel import template_id_for, validate_ampel  # noqa: E402
from app.ampel_templates import AMPEL_TEMPLATES, DEFAULT_TEMPLATE  # noqa: E402
from app.metric_catalog import get_metric  # noqa: E402

_BEIDE = ("von", "bis")
# Bereichs-Schluessel -> (Ampel-Metrik, uebernommene Seiten); Spec §4.
_ZUORDNUNG = {
    "wind_gust": ("gust", _BEIDE), "precipitation_sum": ("precipitation", _BEIDE),
    "temperature_max": ("temperature", ("bis",)), "temperature_min": ("temperature", ("von",)),
    "snow_line": ("snowfall_limit", _BEIDE),
    "temp_max_c": ("temperature", _BEIDE), "gust_max_kmh": ("gust", _BEIDE),
}
# Ampel-Metrik-IDs selbst (z.B. Trip-Bereich "temperature"); Gewitter hat keine Zahlengrenzen.
_DIREKT = set(AMPEL_TEMPLATES[DEFAULT_TEMPLATE]["metrics"]) - {"thunder"}
_FEINE_SCHRITTE = {"°C": 0.1, "mm": 0.1}  # sonst 1 (km/h, %, m, cm)
_ALLE_TAGE = {"today": True, "tomorrow": True, "day_after": True}
_LEER = {"lower": {}, "upper": {}}


def _zahl(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _dict(v: object) -> dict:
    return v if isinstance(v, dict) else {}


def _schritt(mid: str) -> float:
    try:
        return _FEINE_SCHRITTE.get(get_metric(mid).unit, 1)
    except KeyError:
        return 1


def _seite(vorlage: dict, gelb: float, oben: bool) -> tuple[dict, float]:
    """Vorlagen-Seite mit neuem Gelb. Verletzt es die Reihenfolge, wird die
    ganze Seite um die Abweichung von Gelb verschoben (Klemm-Regel)."""
    seite = dict(vorlage)
    alt, seite["yellow"] = seite.get("yellow"), gelb
    rest = [seite[k] for k in ("orange", "red") if seite.get(k) is not None]
    if alt is None or not any(r <= gelb if oben else r >= gelb for r in rest):
        return seite, 0
    delta = round(gelb - alt, 6)
    for k in ("orange", "red"):
        if seite.get(k) is not None:
            seite[k] = round(seite[k] + delta, 6)
    return seite, delta


def _metrik_eintrag(mid: str, band: dict, vorlage: dict) -> tuple[dict | None, list[str]]:
    eintrag, notizen = {}, []
    if band.get("von") is not None:
        eintrag["lower"], d = _seite(vorlage["lower"], band["von"], oben=False)
        if d:
            notizen.append(f"unten verschoben um {d:+g}")
    if band.get("bis") is not None:
        gelb = round(band["bis"] + _schritt(mid), 6)
        eintrag["upper"], d = _seite(vorlage["upper"], gelb, oben=True)
        if d:
            notizen.append(f"oben verschoben um {d:+g}")
    voll = {"lower": eintrag.get("lower", vorlage["lower"]), "upper": eintrag.get("upper", vorlage["upper"])}
    fehler = validate_ampel({"metrics": {mid: voll}})
    return (None, fehler) if fehler else (eintrag, notizen)


def _band_eintragen(baender: dict, key: str, von, bis, quelle: str, bericht: list) -> None:
    ziel = _ZUORDNUNG.get(key) or ((key, _BEIDE) if key in _DIREKT else None)
    if ziel is None:
        bericht.append(f"    nicht zuordenbar: {key} {[von, bis]} ({quelle}): erhalten, nicht migriert")
        return
    mid, seiten = ziel
    for seite, wert in (("von", von), ("bis", bis)):
        if wert is None:
            continue
        if seite not in seiten or not _zahl(wert):
            bericht.append(f"    {quelle} {key}: {seite}={wert} nicht übernommen (gilt für {mid}: {seiten})")
            continue
        band = baender.setdefault(mid, {"quellen": []})
        if seite in band:
            bericht.append(f"    {quelle} {key}: {mid}.{seite} schon belegt, nicht übernommen")
            continue
        band[seite] = wert
        if f"{quelle} {key}" not in band["quellen"]:
            band["quellen"].append(f"{quelle} {key}")


def _baender(obj: dict, bericht: list) -> dict:
    """Ampel-Metrik -> {von, bis, quellen}; ``ideal_ranges`` nur ohne Bereich."""
    baender, gesehen = {}, set()
    for c in obj.get("corridors") or []:
        if not isinstance(c, dict):
            continue
        key, rng = c.get("metric"), list(c.get("range") or []) + [None, None]
        gesehen.add(key)
        if c.get("mark"):
            _band_eintragen(baender, key, rng[0], rng[1], "corridors", bericht)
        elif c.get("notify"):
            bericht.append(f"    Δ-Bereich {key} {rng[:2]} (notify ohne mark): erhalten, keine Ampel-Grenze (S2)")
    for key, b in _dict(_dict(obj.get("display_config")).get("ideal_ranges")).items():
        if key not in gesehen and isinstance(b, dict):
            _band_eintragen(baender, key, b.get("min"), b.get("max"), "ideal_ranges", bericht)
    return baender


def _ampel_planen(obj: dict, bericht: list) -> dict | None:
    alt = obj["display_config"].get("ampel")
    if alt is not None and validate_ampel(alt):
        bericht.append(f"    vorhandene Ampel ungültig, unverändert: {validate_ampel(alt)}")
        return None
    ampel = copy.deepcopy(alt) if isinstance(alt, dict) else {}
    tid = template_id_for(obj)
    ampel.setdefault("template", tid)
    bericht.append(f"    Vorlage: {ampel['template']}")
    metrics = dict(ampel.get("metrics") or {})
    for mid, band in _baender(obj, bericht).items():
        quellen = ", ".join(band["quellen"])
        if mid in metrics:
            bericht.append(f"    {mid}: Ampel vorhanden, nicht überschrieben ({quellen})")
            continue
        eintrag, notizen = _metrik_eintrag(mid, band, AMPEL_TEMPLATES[tid]["metrics"].get(mid, _LEER))
        if eintrag is None:
            bericht.append(f"    übersprungen: {mid} aus {quellen}: {'; '.join(notizen)} (Altdaten erhalten)")
            continue
        metrics[mid] = eintrag
        bericht.append(f"    {mid} aus {quellen} -> {eintrag}" + (f" ({'; '.join(notizen)})" if notizen else ""))
    if metrics:
        ampel["metrics"] = metrics
    return ampel


def _listen(dc: dict):
    """(Ort, Liste) der drei Fundstellen: metrics, channel_layouts, report_layouts."""
    if isinstance(dc.get("metrics"), list):
        yield "metrics", dc["metrics"], True
    for k, liste in _dict(dc.get("channel_layouts")).items():
        yield f"channel_layouts.{k}", liste, True
    for r, kanaele in _dict(dc.get("channel_layouts_per_report")).items():
        for k, liste in _dict(kanaele).items():
            yield f"channel_layouts_per_report.{r}.{k}", liste, True
    yield "active_metrics", dc.get("active_metrics"), False
    for k, liste in _dict(dc.get("channel_active_metrics")).items():
        yield f"channel_active_metrics.{k}", liste, False


def _ist(e: object, mid: str, key: str) -> bool:
    return e == key or (isinstance(e, dict) and e.get("metric_id") == mid)


def _an(e: object) -> bool:
    return isinstance(e, str) or e.get("enabled", True) is not False


def _gewitter_an(liste: list, ort: str, trip_liste: bool, bericht: list) -> None:
    """Gespeicherte CAPE-Auswahl -> Gewitter aktiv (CAPE bleibt stehen)."""
    cape = next((e for e in liste if _ist(e, "cape", "cape_max_jkg") and _an(e)), None)
    if cape is None:
        return
    gewitter = next((e for e in liste if _ist(e, "thunder", "thunder_level_max")), None)
    if gewitter is not None and _an(gewitter):
        return
    if gewitter is not None:
        gewitter["enabled"] = True
    elif isinstance(cape, str):
        liste.append("thunder_level_max")
    else:
        liste.append({"metric_id": "thunder", "enabled": True} if trip_liste
                     else {"metric_id": "thunder", "aggregation": "max"})
    bericht.append(f"    CAPE-Auswahl in {ort} -> Gewitter aktiv")


def _listen_angleichen(dc: dict, bericht: list) -> None:
    for ort, liste, trip_liste in list(_listen(dc)):
        if not isinstance(liste, list):
            continue
        for e in (e for e in liste if isinstance(e, dict)):
            if e.get("sms_threshold") is not None:
                bericht.append(f"    sms_threshold {e.get('metric_id')}={e['sms_threshold']} in {ort}: "
                               "erhalten, ohne Wirkung (E1)")
            h = e.get("horizons")
            if isinstance(h, dict) and not all(h.get(t, True) for t in _ALLE_TAGE):
                e["horizons"] = {**h, **_ALLE_TAGE}
                bericht.append(f"    horizons {e.get('metric_id')} in {ort} -> alle Tage")
        _gewitter_an(liste, ort, trip_liste, bericht)


def _datei_planen(pfad: Path, bericht: list) -> tuple[dict, bool] | None:
    text = pfad.read_text(encoding="utf-8")
    try:
        obj = json.loads(text)
    except ValueError:
        bericht.append("    unlesbar, übersprungen")
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("display_config"), dict):
        bericht.append("    kein display_config: unverändert (Rückfall auf die Vorlage beim Lesen)")
        return None
    neu = copy.deepcopy(obj)
    ampel = _ampel_planen(neu, bericht)
    if ampel is not None:
        neu["display_config"]["ampel"] = ampel
    _listen_angleichen(neu["display_config"], bericht)
    return (neu, text.endswith("\n")) if neu != obj else None


def _eigene_vorlagen(udir: Path) -> list[str]:
    try:
        presets = json.loads((udir / "metric_presets.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [f"  eigene Vorlage {p.get('name')!r} ({p.get('id')}) ohne Ampel: unverändert, Rückfall allgemein"
            for p in presets if isinstance(p, dict) and not p.get("ampel")] if isinstance(presets, list) else []


def _nutzer_planen(udir: Path) -> tuple[list, list[str]]:
    plan, bericht = [], [f"== Nutzer {udir.name} =="]
    for pfad in sorted((udir / "briefings").glob("*.json")):
        zeilen: list[str] = []
        ergebnis = _datei_planen(pfad, zeilen)
        status = "wird geändert" if ergebnis else "unverändert"
        bericht += [f"  {pfad.relative_to(udir)}: {status}", *zeilen]
        if ergebnis:
            plan.append((pfad, *ergebnis))
    return plan, bericht + _eigene_vorlagen(udir)


def _sichern(udir: Path, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-2792-{udir.name}-{stempel}.tar.gz"
    with tarfile.open(ziel, "w:gz") as tar:
        for teil in ("briefings", "metric_presets.json"):
            if (udir / teil).exists():
                tar.add(udir / teil, arcname=f"{udir.name}/{teil}")
    return ziel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1
    nutzer = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith((".", "_"))]
    plaene = {}
    for udir in nutzer:  # Phase 1: alles planen, nichts schreiben
        plan, bericht = _nutzer_planen(udir)
        print("\n".join(bericht))
        if plan:
            plaene[udir] = plan
    if not plaene:
        print("Nichts zu tun: alle Dateien bereits migriert.")
    if not args.execute or not plaene:
        print("" if args.execute else "Probelauf: nichts geschrieben (--execute zum Ausführen).")
        return 0
    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for udir in plaene:  # Phase 2: erst alle Sicherungen ...
            print(f"Sicherung geschrieben: {_sichern(udir, backup_dir, stempel)}")
    except OSError as exc:
        print(f"Error: Sicherung nach '{backup_dir}' fehlgeschlagen, nichts geschrieben: {exc}", file=sys.stderr)
        return 1
    for plan in plaene.values():  # ... dann schreiben
        for pfad, neu, newline in plan:
            pfad.write_text(json.dumps(neu, indent=2, ensure_ascii=False) + ("\n" if newline else ""),
                            encoding="utf-8")
    print(f"Migration abgeschlossen: {sum(map(len, plaene.values()))} Datei(en) geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
