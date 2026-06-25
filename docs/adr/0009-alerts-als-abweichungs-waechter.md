# ADR-0009: Alerts sind Abweichungs-Wächter, keine absoluten Schwellen

- **Status:** Akzeptiert
- **Datum:** 2026-06-16 (Epic #813)
- **Bezug:** GitHub-Epic #813 (Slices #816, #817), Issues #821, #822, #864/#859

## Kontext

Ein Nutzer erhält ein Trip-Briefing mit der zum Zeitpunkt X gültigen Vorhersage und plant danach.
Die eigentliche Gefahr ist nicht „das Wetter ist schlecht" (das stand ggf. schon im Briefing),
sondern dass sich die Lage **seit dem Briefing wesentlich geändert** hat und der Nutzer mit veralteten
Annahmen unterwegs ist. Eine Alert-Logik auf Basis **absoluter** Schwellen (z. B. „warne bei Wind >
50 km/h") würde bei jedem ohnehin bekannten Schlechtwetter feuern — Lärm statt Signal — und den
eigentlichen Zweck verfehlen.

## Entscheidung

Alerts sind **Abweichungs-Wächter**: Sie melden, wenn der aktuelle Nowcast **deutlich vom zuletzt
versendeten Briefing abweicht** (Δ-Abweichung gegen einen gespeicherten Briefing-Snapshot), **nicht**
gegen eine absolute Schwelle und **nicht** gegen den Vortag.

- Beim Briefing-Versand wird ein **Snapshot** der prognostizierten Werte persistiert
  (`alert_state`).
- Der Alert-Lauf vergleicht den Nowcast gegen diesen Snapshot und feuert bei Überschreiten der
  **pro-Metrik-Δ-Empfindlichkeit** (Empfindlichkeitsstufen statt fixer Presets — #864/#859).
- Dedup ist **feld-selektiv**: dieselbe Abweichung feuert nicht doppelt (#821); Cooldown/Throttle
  verhindern Wiederholungs-Spam.
- Die Alert-Mail benennt **Etappe, Segment-km und Onset-Zeit** der Abweichung (#822, #801/#803).

## Verworfene Alternativen

- **Absolute Schwellen** („warne bei Regen > X mm") — verworfen: feuert bei bereits bekanntem
  Schlechtwetter → Alarm-Müdigkeit; ignoriert, was der Nutzer bereits weiß.
- **Vortagsvergleich** — verworfen: der Bezugspunkt ist die **Entscheidungsgrundlage des Nutzers**
  (das letzte Briefing), nicht ein willkürliches Kalenderfenster.

## Konsequenzen

- **Positiv:** Alerts sind signalstark und handlungsrelevant — sie melden genau das, was die
  bisherige Planung umwirft.
- **Negativ / Preis:** Erfordert Briefing-Snapshots als zusätzlichen Persistenz-Zustand
  (`alert_state`) und eine saubere Dedup-/Cooldown-Mechanik; ohne gesendetes Briefing gibt es keinen
  Vergleichsanker.
- **Folgepflichten:** Neue Alert-Funktionen müssen am Abweichungs-Modell andocken (Snapshot-Vergleich),
  nicht absolute Schwellen einführen. Der Briefing-Snapshot muss bei jedem Versand aktuell gehalten
  werden.
