# Spec: CAPE-Ampel-Kalibrierung + Zusammenfassung↔Tabelle-Konsistenz

- **Status:** Approved (PO-go 2026-07-22)
- **created:** 2026-07-22
- **Workflow:** fix-briefing-grid-and-summary
- **Typ:** Bugfix

## Kontext (belegter Hergang)

Der KHW-Trip (5f534011) verlor auf dem Handy das Tabellengitter, weil der Nutzer
cape **bewusst** von „friendly/Ampel" auf „roh" stellte (die CAPE-Ampel zeigte
immer grün). cape war die letzte ampel-fähige Metrik im „friendly"-Modus; das
Mobil-Gitter (`_render_mobile_compact_rows`, email/html.py) ist an
`build_html_indicator_keys(dc)` (≥1 ampel-fähige Metrik friendly) gekoppelt →
leer → gitterloser `<pre>`.

**Sofort-Restore (bereits erledigt, 2026-07-22):** in
`briefings/5f534011.json` cape `use_friendly_format` False→True (RMW+Merge,
Backup `.backups/briefings-5f534011-pre-friendly-restore-20260722-150610.json`).
Gitter kommt beim nächsten Briefing zurück. Diese Spec macht cape dauerhaft
sinnvoll (Fix A) und behebt die separate Kurzform-Divergenz (Fix B).

## Root Cause

- **CAPE-Ampel „immer grün":** KEIN Code-Fehler. `severity_for("cape", v)`
  wendet `display_thresholds={yellow:1000, orange:2500, red:3500}`
  (Standard-Konvektionsskala, Flachland) korrekt an. Reale CAPE-Werte im
  Gebirge liegen meist <1000 → dauergrün, während „⚡" (thunder-Feld) warnt.
  Berg-Gewitter triggern orographisch bei niedrigerem CAPE → Schwellen zu hoch.
- **Kurzform↔Tabelle:** Kurzform-Kanäle (compact_summary, sms_trip, narrow)
  werten das Tagesfenster (`day_window.build_day_window_points`, 04–19 h,
  Segment-1-Start 04:00) aus; die Stundentabelle (`trip_report
  ._extract_hourly_rows`) nur die echte Wanderzeit. Peak außerhalb der
  Tabellenstunden → Warnung ohne Deckung (belegt: 12:00-KHW-Mail warnt
  „⚡ 16:00–18:00 / Regen ab 16:00", Tabelle 16:00/18:00 = `Regen 0.0`,
  `Gewitter –`).

## Acceptance Criteria

- **AC-1:** (CAPE-Kalibrierung) Given eine CAPE-Ampel-Zelle/Pille, When der Wert
gefärbt wird, Then gilt: grün < 300, gelb 300–799, orange 800–1499, rot ≥ 1500
J/kg — d. h. `get_metric("cape").display_thresholds ==
{yellow:300, orange:800, red:1500}` und `severity_for("cape", v)` liefert an den
Grenzen 300/800/1500 die jeweils höhere Stufe. (Ersetzt keine bestehende Regel;
Prüfdatum n/a — reine Datenkalibrierung.)

- **AC-2:** (Kurzform↔Tabelle konsistent) Given eine Etappe mit Gewitter-/Regen-/
Böen-Peak außerhalb der in den Stundentabellen gezeigten Stunden, When die
Kurzzusammenfassung/SMS/Telegram-Fußzeile erzeugt wird, Then erscheint dort
keine Warnung ohne deckende Tabellenzeile — die Kurzform wertet dieselbe
Stundenmenge aus, die die Tabellen zeigen.

- **AC-3:** (Tests) Given der Fix, When die Tests laufen, Then (a) prüft ein Test
`severity_for("cape", …)` an den neuen Grenzen (299→green, 300→yellow,
799→yellow, 800→orange, 1499→orange, 1500→red); (b) reproduziert ein Test die
Kurzform↔Tabelle-Divergenz aus Nutzersicht (rot vor Fix, grün nach Fix).

- **AC-4:** (Kanal-Sweep) Given der Fix, When SMS und Telegram desselben Pfads
geprüft werden, Then gilt AC-2 auch dort, bevor „erledigt" gesagt wird.

## Nicht-Ziele / offen als Folgeschritt

- **Gitter vom Ampel-Modus entkoppeln** (bordierte Tabelle auch im Roh-Modus):
  Robustheit, NICHT Teil dieser Spec. Durch Fix A + Restore ist das akute
  Problem gelöst; als optionaler Folge-Slice offen.
- Kein Mail-Layout-Redesign. Gitter-CSS (#900/#902/#911) unangetastet.

## Invarianten

- Read-Modify-Write-Merge bei Persistenz (kein Datenverlust).
- CAPE-Schwellenänderung wirkt global (Katalog) — akzeptiert, da einziger
  Produktivnutzer betroffen; keine andere Metrik ändert sich.
