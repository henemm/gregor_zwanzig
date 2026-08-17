# ADR-0056: Rollierender Alarm-Anker statt ausschließlich briefing-gebundenem Snapshot

- **Status:** Akzeptiert
- **Datum:** 2026-08-16
- **Bezug:** Issue #1916 (Alarm-Vergleichsbasis rollierend + Referenz-Zeitpunkt sichtbar),
  löst ADR-0009 (Teil "Snapshot wird beim Briefing-Versand persistiert") ab, Bezug #1897
  (gescheiterter Briefing-Versand), #823 (Tagesgrenze, bleibt unverändert), #818/#1667
  (Radar-Alert-Unterdrückung, bleibt unverändert)

## Kontext

ADR-0009 legt fest: "Beim Briefing-Versand wird ein Snapshot der prognostizierten Werte
persistiert" und "ohne gesendetes Briefing gibt es keinen Vergleichsanker." Das war bewusst so
konstruiert — der Referenzpunkt sollte die tatsächliche Entscheidungsgrundlage des Nutzers sein
(das zuletzt gelesene Briefing), nicht ein beliebiger technischer Zeitpunkt.

In der Praxis erwies sich diese enge Kopplung als Schwachstelle: Scheitert ein Briefing-Versand
(Prozessabbruch, siehe #1897), bleibt der Anker auf dem Stand des letzten *erfolgreichen*
Briefings stehen — im dokumentierten Fall vom 2026-08-16 verglich ein Alarm einen ~24h alten
Wert (Vorabend-Briefing) statt eines aktuellen. Der Nutzer erhält damit einen Alarm gegen eine
Vergleichsbasis, die er selbst nicht mehr als "sein letztes Briefing" wiedererkennt — der
eigentliche Zweck von ADR-0009 (Alarm = "was hat sich seit deiner Planungsgrundlage geändert")
wird unterlaufen, sobald ein einzelner Versand scheitert.

## Entscheidung

Der Δ-Vergleichsanker ist nicht mehr ausschließlich an einen erfolgreichen Briefing-Versand
gebunden. Er wird zusätzlich **rollierend** über einen separaten, dritten Snapshot-Typ
nachgezogen:

- **(a)** bei jedem tatsächlich versendeten Alarm (verallgemeinert "Referenz-Reset bei
  Briefing" auf "Referenz-Reset bei jedem erfolgreichen Δ-Ereignis"),
- **(b)** opportunistisch, wenn der wirksame Anker (Briefing- oder rollierender Anker, jeweils
  der jüngere) eine Alterungs-Ceiling (Richtwert 4h, siehe `docs/specs/modules/trip_alert.md`)
  überschreitet, auch ohne ausgelösten Alarm.

Der rollierende Anker ist ein **eigener Speicherort**, getrennt vom Briefing-Anker
(`{trip_id}_{date}.json`) — dieser bleibt unverändert als eingefrorene Briefing-Prognose für
die Radar-Alert-Unterdrückung (#818/#1667) erhalten. Die #823-Tagesgrenze (kein "heute gegen
morgen") gilt identisch auch für den rollierenden Anker.

**Explizit NICHT verworfen aus ADR-0009:** das Grundprinzip "Abweichungs-Wächter, nicht
absolute Schwelle, nicht Vortagsvergleich" bleibt unangetastet. Ebenso bleibt die
Signifikanz-Prüfung gegen den jeweils gültigen Anker (nicht gegen den letzten Messwert)
erhalten — ein naives "Anker bei jedem Check-Lauf ohne Alarm überschreiben" würde die
Trend-Erkennung brechen (ein langsamer, kumulativer Anstieg über mehrere Check-Zyklen, der pro
Schritt unter der Schwelle bleibt, würde nie mehr auslösen) und ist deshalb bewusst NICHT die
gewählte Umsetzung.

## Verworfene Alternativen

- **Anker bei jedem Check-Lauf neu schreiben** (unabhängig von Alarm/Ceiling) — verworfen:
  verkleinert das Δ-Vergleichsfenster auf ein einzelnes Check-Intervall (15 Min) und bricht
  damit die Erkennung langsamer, kumulativer Trends (Regressionsrisiko, s. `trip_alert.md`
  AC-9).
- **`save_dated`/`load_dated` (Briefing-Anker-Datei) für den rollierenden Anker wiederverwenden**
  — verworfen: würde die Radar-Alert-Unterdrückung (#818/#1667) aushebeln, die genau diese
  Datei als eingefrorene Briefing-Prognose liest.
- **Nur Sichtbarkeit ändern, Snapshot-Mechanik unangetastet lassen** — verworfen: löst das
  ursprüngliche #1916-Symptom (bis zu 24h alte Basis nach gescheitertem Briefing) nicht, macht
  es nur sichtbar statt es zu beheben.

## Konsequenzen

- **Positiv:** Ein einzelner gescheiterter Briefing-Versand friert die Alarm-Erkennung nicht
  mehr für Stunden auf einem veralteten Stand ein; die Vergleichsbasis erneuert sich spätestens
  nach der Alterungs-Ceiling automatisch.
- **Negativ / Preis:** Ein dritter Snapshot-Typ und ein zweiter Schreibpfad (zusätzlich zum
  Briefing-Anker) erhöhen die Komplexität von `_get_cached_weather()` (Anker-Prioritätskette:
  Briefing-Anker vs. rollierender Anker vs. undatierter Fallback). Der neue Schreibpfad darf
  das Alert-Melde-Gedächtnis nicht mit zurücksetzen (sonst Doppelmeldungen) — braucht einen
  eigenen, schlankeren Pfad als `write_anchor_and_reset_memory()`.
- **Folgepflichten:** Neue Alert-Funktionen, die den Δ-Vergleichsanker berühren, müssen die
  Drei-Wege-Unterscheidung (Briefing-Anker / rollierender Anker / Fallback) respektieren, nicht
  nur den Briefing-Anker annehmen. Die Trend-Erkennungs-Invariante (AC-9 in
  `docs/specs/modules/trip_alert.md`) ist bei jeder künftigen Änderung an der Schreiblogik als
  Regressionstest zu erhalten.
