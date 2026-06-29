# ADR-0011: Alert-Render-System — ein Backend-Renderer, Registry als Single Source

- **Status:** Akzeptiert
- **Datum:** 2026-06-29
- **Bezug:** GitHub-Issue #914 (Issue 27), `docs/context/alert-mail-design.md`, ADR-0007 (Daten statt Empfehlungen), ADR-0009 (Alerts als Abweichungs-Wächter)

## Kontext

Ein ausgelöster Abweichungs-Alert soll generisch in vier Kanäle gerendert werden
(Betreff · E-Mail · Telegram · SMS). Heute ist die Alert-Formatierung über drei
getrennte Renderer verteilt, der Betreff ist statisch, und die SMS-Kurz-Codes
existieren **dreifach und widersprüchlich** (`metric_catalog.compact_label`,
`sms_trip.SMS_SYMBOL_BY_METRIC`, Frontend `ChannelFidelitySMS.SMS_TOK`; z. B.
Gewitter „⚡" vs. „TH:", Schneefallgrenze „SG" vs. „SFL").

Das Issue empfiehlt, die Renderlogik **zweimal** zu implementieren — Python für den
Versand, TypeScript für die Live-Vorschau — und beide über gemeinsame Fixtures
synchron zu halten. Randbedingungen: Das Frontend ist ein **Desktop-Planungstool**
(unterwegs zählen nur die echten E-Mails/SMS, die ohnehin das Backend erzeugt); es
existiert bereits ein Muster, bei dem die Alert-Vorschau fertiges HTML vom Backend
zieht (`POST /api/trips/{id}/alert-preview`), sowie ein `/api/metrics`-Endpunkt, über
den das Frontend Metrik-Stammdaten bezieht.

## Entscheidung

1. Die Alert-Renderlogik lebt **ausschließlich im Python-Backend** als reine
   Funktionen über ein `AlertMessage`-Modell (`render_subject/email/telegram/sms`),
   mit den abgeleiteten Größen (Pfeil, Δ%, über/unter, severity, km-Spanne) als
   **einmaligen** gemeinsamen Helfern.
2. Die Live-Vorschau im Frontend konsumiert die fertig gerenderten Kanäle über einen
   Backend-Endpunkt (Erweiterung des bestehenden `alert-preview`-Musters). Es wird
   **kein** zweiter Renderer in TypeScript gebaut.
3. `metric_catalog.py` ist die **Single Source** für alle render-relevanten
   Metrik-Stammdaten — inkl. `sms_code`, `decimals` und Vergleichsrichtung (`cmp`).
   Doppelte Mappings werden entfernt; die nötigen Felder über `/api/metrics`
   ausgespielt.

## Verworfene Alternativen

- **Zwei Renderer (Python + TypeScript), Issue-Vorschlag** — verworfen: dauerhafte
  Doppelpflege jeder nicht-trivialen Renderregel (severity-Sortierung, SMS-Längen-
  Budget mit `+k`-Überlauf, GSM-7-Zwang). Der einzige Vorteil (Sofort-Render im
  Browser) hat für ein Desktop-Planungstool keinen Produktwert.
- **Renderer aus Python nach TypeScript generieren (Codegen)** — verworfen: zusätzliche
  Build-Komplexität ohne Nutzen, da der Endpunkt-Weg bereits etabliert ist.

## Konsequenzen

- **Positiv:** Genau eine Implementierung; kein Auseinanderdriften; jede künftige
  Format-Änderung an einer Stelle. Constraint C10 (backend-/frontend-identisch) wird
  durch *eine* Quelle stärker erfüllt als durch zwei synchron gehaltene.
- **Negativ / Preis:** Die Vorschau braucht eine (entprellte) Server-Anfrage statt
  Sofort-Render. Für das Desktop-Planungstool unkritisch.
- **Folgepflichten:** Neue alert-fähige Metriken bekommen ihren `sms_code`/`cmp`/
  `decimals` **im Katalog** (nicht im Renderer); Frontend rendert Alert-/Kanal-Inhalte
  nicht eigenständig nach, sondern zeigt Backend-Ergebnisse an.
