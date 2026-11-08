#!/usr/bin/env python3
"""Migration Issue #2793 S2a: Altstufen ``metric_alert_levels`` -> „Alarm ab“ (ADR-0106 P3).

Spec docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md §5 (AC-15..AC-17).
Je Nutzer ``<root>/<uid>/briefings/*.json`` (Trip und Vergleich): Altschluessel
wie der Loader normalisieren, je Katalog-ID relativ zur Vorgabe ``V`` der
Vorlage selbst abbilden (Vorlagen-ID ueber die S1-Rueckfallkette; ein vorhandenes
``alarm_ab`` im Abo ist nicht V): off -> never, standard -> V, sensibel -> eine
Stufe empfindlicher, entspannt -> red; mehrere Schluessel: empfindlichster.
Geschrieben wird NUR ``display_config.ampel.metrics.<id>.alarm_ab`` plus Merker
``display_config.alarm_ab_migration``; ``metric_alert_levels`` bleibt (D4).
Ablauf, Sicherung, Sperre und atomares Schreiben wie
``scripts/migrate_2792_profil_ampel.py`` (dessen ``schreiben`` wird genutzt).

Exit: 0 fertig, 1 offene Dateien (erneut laufen lassen), 2 ungueltige Ampel mit
Altstufen (manuell pruefen).

Usage: python3 scripts/migrate_2793_alarm_ab.py --root <data/users> [--backup-dir <p>] [--execute]
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
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from app.ampel import template_id_for, validate_ampel  # noqa: E402
from app.ampel_templates import AMPEL_TEMPLATES  # noqa: E402
from app.loader import _ALT_ALERT_LEVEL_KEYS, _migrate_metric_alert_levels  # noqa: E402  (wie beim Laden)
from migrate_2792_profil_ampel import schreiben  # noqa: E402  (Sperre, Inhaltsvergleich, atomar)

MERKER, MERKER_WERT = "alarm_ab_migration", "2793"
UNGUELTIG = "ungueltig"  # Altstufen vorhanden, Ampel ungueltig: manuell pruefen (Exit 2)
# AlertMetric-Schluessel -> Katalog-ID (Spec §5).
_ABBILDUNG = {
    "wind_gust": "gust", "precipitation_sum": "precipitation", "precipitation_change": "precipitation",
    "temperature_min": "temperature", "temperature_max": "temperature", "temperature_change": "temperature",
    "wind_change": "wind", "thunder_level": "thunder", "visibility": "visibility", "fresh_snow": "fresh_snow",
}
_D4 = "bleibt bis S7 auf der Δ-Stufe (D4), wirksam"
_NICHT_ABGEBILDET = {
    "cape": "geht über die Gewitterstufe ein (P1)", "freezing_level": _D4, "snow_line": _D4,
    "thunder_onset": _D4, "precipitation_heavy_onset": _D4, "humidity": "Vorbote, nie Auslöser (ADR-0010)",
}
_EMPFINDLICHER = {"never": "red", "red": "orange", "orange": "yellow", "yellow": "yellow"}
_RANG = {"yellow": 1, "orange": 2, "red": 3, "never": 4}  # klein = empfindlicher


def _stufe(alt: str, vorgabe: str, mid: str) -> str | None:
    if alt == "sensibel":
        neu = _EMPFINDLICHER[vorgabe]
        return "orange" if mid == "thunder" and neu == "yellow" else neu
    return {"off": "never", "standard": vorgabe, "entspannt": "red"}.get(alt)


def _abbilden(levels: dict, vorgaben: dict, bericht: list) -> dict:
    """Katalog-ID -> alarm_ab; Konflikte und Nicht-Abgebildetes in den Bericht."""
    quellen: dict[str, list] = {}
    for alt_key in (k for k in levels if k in _ALT_ALERT_LEVEL_KEYS):
        bericht.append(f"    Altschlüssel {alt_key} -> {_ALT_ALERT_LEVEL_KEYS[alt_key] or 'verworfen'} (wie Loader)")
    for key, alt in _migrate_metric_alert_levels(levels).items():
        if key not in _ABBILDUNG:
            grund = _NICHT_ABGEBILDET.get(key, "unbekannter Schlüssel")
            bericht.append(f"    nicht abgebildet: {key}={alt} ({grund}), erhalten")
            continue
        mid = _ABBILDUNG[key]
        neu = _stufe(alt, vorgaben.get(mid, "never"), mid) if isinstance(alt, str) else None
        if neu is None:
            bericht.append(f"    unbekannter Wert: {key}={alt}, erhalten, nicht abgebildet")
            continue
        quellen.setdefault(mid, []).append((key, alt, neu))
    ergebnis = {}
    for mid, liste in quellen.items():
        ergebnis[mid] = min((neu for _, _, neu in liste), key=_RANG.__getitem__)
        herkunft = ", ".join(f"{k}={a}->{n}" for k, a, n in liste)
        if len({n for _, _, n in liste}) > 1:
            bericht.append(f"    Konflikt {mid}: {herkunft}; gilt der empfindlichste: {ergebnis[mid]}")
        bericht.append(f"    {mid}: alarm_ab {ergebnis[mid]} (Vorgabe {vorgaben.get(mid, 'never')}; aus {herkunft})")
    return ergebnis


def _datei_planen(pfad: Path, bericht: list) -> tuple[dict, str] | str | None:
    text = pfad.read_text(encoding="utf-8")
    try:
        obj = json.loads(text)
    except ValueError:
        bericht.append("    unlesbar, übersprungen")
        return None
    dc = obj.get("display_config") if isinstance(obj, dict) else None
    if not isinstance(dc, dict) or not isinstance(dc.get("metric_alert_levels"), dict) \
            or not dc["metric_alert_levels"]:
        bericht.append("    keine Altstufen: unverändert (Vorgabe der Vorlage gilt)")
        return None
    if dc.get(MERKER) == MERKER_WERT:
        bericht.append("    bereits migriert (Merker)")
        return None
    if validate_ampel(dc.get("ampel")):
        bericht.append(f"    Ampel ungültig, nicht migriert: {'; '.join(validate_ampel(dc['ampel']))}")
        return UNGUELTIG
    tid = template_id_for(obj)  # Rueckfallkette wie S1; V ist die Vorgabe der Vorlage selbst (F1)
    bericht.append(f"    Vorlage: {tid}")
    vorgaben = {mid: e.get("alarm_ab", "never") for mid, e in AMPEL_TEMPLATES[tid]["metrics"].items()}
    neu = copy.deepcopy(obj)
    _eintragen(neu["display_config"], _abbilden(dc["metric_alert_levels"], vorgaben, bericht), bericht)
    neu["display_config"][MERKER] = MERKER_WERT
    return neu, text


def _eintragen(dc: dict, stufen: dict, bericht: list) -> None:
    """Read-Modify-Write: nur ``alarm_ab`` je Metrik-Zeile, alles andere bleibt."""
    if not stufen:
        return
    ampel = dc["ampel"] if isinstance(dc.get("ampel"), dict) else {}
    metrics = ampel["metrics"] if isinstance(ampel.get("metrics"), dict) else {}
    for mid, stufe in stufen.items():
        zeile = metrics.setdefault(mid, {})
        if zeile.get("alarm_ab") not in (None, stufe):
            bericht.append(f"    {mid}: eigenes alarm_ab {zeile['alarm_ab']} ersetzt durch {stufe}")
        zeile["alarm_ab"] = stufe
    ampel["metrics"], dc["ampel"] = metrics, ampel


def _nutzer_planen(udir: Path) -> tuple[list, list[str], int]:
    plan, bericht, ungueltig = [], [f"== Nutzer {udir.name} =="], 0
    for pfad in sorted((udir / "briefings").glob("*.json")):
        zeilen: list[str] = []
        ergebnis = _datei_planen(pfad, zeilen)
        ungueltig += ergebnis == UNGUELTIG
        geplant = isinstance(ergebnis, tuple)
        bericht += [f"  {pfad.relative_to(udir)}: {'wird geändert' if geplant else 'unverändert'}", *zeilen]
        if geplant:
            plan.append((pfad, *ergebnis))
    return plan, bericht, ungueltig


def planen(root: Path) -> tuple[dict, list[str], int]:
    """Phase 1: alle Nutzer planen, nichts schreiben. Nutzer = echte Ordner.
    Liefert Plaene, Bericht und die Zahl der Dateien mit ungueltiger Ampel und Altstufen."""
    plaene, bericht, ungueltig = {}, [], 0
    for udir in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
        plan, zeilen, n = _nutzer_planen(udir)
        bericht, ungueltig = bericht + zeilen, ungueltig + n
        if plan:
            plaene[udir] = plan
    return plaene, bericht, ungueltig


def _abschluss(ungueltig: int, code: int) -> int:
    """Exit 1 = offene Dateien (erneut laufen lassen), Exit 2 = ungueltige Ampel mit Altstufen."""
    if ungueltig:
        print(f"{ungueltig} Dateien mit ungültiger Ampel nicht migriert: manuell prüfen")
    return code or (2 if ungueltig else 0)


def _sichern(udir: Path, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-2793-{udir.name}-{stempel}.tar.gz"
    with tarfile.open(ziel, "w:gz") as tar:
        tar.add(udir / "briefings", arcname=f"{udir.name}/briefings")
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
    plaene, bericht, ungueltig = planen(root)
    print("\n".join(bericht))
    if not plaene and not ungueltig:
        print("Nichts zu tun: alle Dateien bereits migriert.")
    if not args.execute or not plaene:
        print("" if args.execute else "Probelauf: nichts geschrieben (--execute zum Ausführen).")
        return _abschluss(ungueltig, 0)
    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for udir in plaene:  # Phase 2: erst alle Sicherungen, dann schreiben
            print(f"Sicherung geschrieben: {_sichern(udir, backup_dir, stempel)}")
    except OSError as exc:
        print(f"Error: Sicherung nach '{backup_dir}' fehlgeschlagen, nichts geschrieben: {exc}", file=sys.stderr)
        return 1
    offen = schreiben(plaene)
    print(f"Migration abgeschlossen: {sum(map(len, plaene.values())) - len(offen)} Datei(en) geschrieben.")
    for zeile in offen:
        print(f"Error: {zeile} -- erneut laufen lassen", file=sys.stderr)
    return _abschluss(ungueltig, 1 if offen else 0)


if __name__ == "__main__":
    sys.exit(main())
