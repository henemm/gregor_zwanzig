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

## Nachtrag 2026-08-01 (#1435 E3b)

Die am 2026-06-30 gewährte Ausnahme, wonach Ziel 3 („doppelte Mappings entfernen")
nur für den Alert-`sms_code` gilt und **nicht** für die Briefing-SMS-Token-Grammatik
(festgehalten in `docs/specs/_archive/modules/issue_917_alert_renderer.md`, Abschnitt
„Architektur-Entscheidung (ADR)", samt der dortigen AC-9), ist **widerrufen**. Ziel 3
gilt ab sofort auch für Schneehöhe, Schneefallgrenze und Neuschnee im
Briefing-SMS-Pfad: Diese Kürzel stammen jetzt aus `metric_catalog.sms_code`
(`SD`/`SL`/`NS`) statt aus einem eigenen Trip-Vokabular (`SN`/`SFL`/`SN24+`).

Bewusst **nicht** widerrufen bleiben zwei Sonderfälle: `TH:` (Grammatikform mit
Doppelpunkt; das Register kennt nur `TH`) und das Quartett `WC`/`FN`/`FK`/`FD` für
die gefühlte Temperatur (eine Registergröße, vier Kürzel — strukturell nicht aus
einem einzelnen `sms_code`-Feld ableitbar). `AV` (Lawinenstufe) bleibt außerhalb,
weil das Register dafür keine Größe führt.

Der Status dieses ADR bleibt **Akzeptiert** und unverändert — E3b nimmt keine
Entscheidung zurück, sondern erfüllt Ziel 3 vollständiger. Spec:
`docs/specs/modules/fix_1435_e3b_sms_kuerzel.md`.

## Nachtrag 2026-08-15 (#1856 E7) — die Sonderfälle sind jetzt bewacht

Die im E3b-Nachtrag oben **bewusst nicht widerrufenen** Sonderfälle — `TH:` und das
Quartett `WC`/`FN`/`FK`/`FD` — standen bis hierher nur als Prosa in diesem ADR und als
Kommentar im Code. Mit E7 sind sie **maschinenlesbar**: Der Wächter
`tests/helpers/metrik_listen_scan.py` führt `SMS_MULTI_SYMBOLS_BY_METRIC`,
`SMS_SYMBOL_BY_METRIC` und `SMS_SYMBOL_GRAMMAR` in seiner Registrierung und prüft, dass
jede dort geführte Kennung im Register existiert.

Zwei Zusicherungen kommen hinzu, beide in `tests/unit/test_sms_token_symbol_register_ratchet.py`
(fünfte Prüfstelle neben den vier aus E3b, die unverändert bleiben):

- **Kein Kürzel bezeichnet zwei verschiedene Größen** — getrennt geprüft für den Trip-SMS-Weg
  (über `_kurzform_kuerzel()`) und den Register-Weg (`sms_code`), nie über die Wege hinweg.
- Gruppiert wird nach **Metrik-Kennung**, nicht nach Kürzel-Wert: `TH` erscheint in beiden
  Trip-Tabellen, beide Male für `thunder`. Leere Kürzel werden übersprungen — `confidence`
  führt bewusst keines (28 Register-Einträge, 27 Kürzel).

**Ausdrücklich nicht** geprüft wird die Gleichheit zwischen Trip-SMS-Weg und Register-Weg. Die
beiden Wege sind bewusst verschieden (Trip-SMS sendet Tagesauswertungen `FK`/`FD`/`WC`,
Vergleichs- und Alarm-SMS senden `TF` aus `get_sms_code()`, siehe `comparison.py:647` und
`alert/render.py:93`). Eine Gleichheitsprüfung hätte drei entschiedene Zustände als Fehler
gemeldet und wäre nach dem ersten Lauf taub gewesen — verworfen, Begründung in der Spec unter
„Verworfene Alternativen".

Status unverändert **Akzeptiert**. Spec: `docs/specs/modules/fix_1856_e7_metrik_listen_waechter.md`.

## Nachtrag 2026-08-06 (#923)

Der im Kontext-Abschnitt genannte dritte Fall der dreifachen SMS-Kürzel-Kopie
(Frontend `ChannelFidelitySMS.SMS_TOK`) ist geschlossen. `ChannelFidelitySMS.svelte`
und `ChannelPreviewCard.svelte` (Metrik-Editor-Vorschau für den SMS-Kanal)
rendern nicht mehr über eine eigene, hartcodierte TypeScript-Simulation
(`SMS_TOK`/`smsRender`), sondern konsumieren die fertig gerenderte Zeile über
einen neuen zustandslosen Backend-Endpunkt `POST
/api/_validator/sms-fidelity-preview` (`api/routers/validator.py`), der
dieselben Funktionen (`build_token_line()`, `render_line_with_survivors()`) wie
der echte Versandpfad aufruft — analog zur bereits umgesetzten Alert-Vorschau
(#918). Damit gilt Entscheidungspunkt 2 dieses ADR jetzt auch für die
Briefing-SMS-Editor-Vorschau, nicht mehr nur für Alerts. Spec:
`docs/specs/modules/fix_923_sms_fidelity_backend.md`.

**Korrektur 2026-08-06 (#923b):** Die oben beschriebene Verdrahtung war korrekt
gebaut, aber an die falschen Komponenten angeschlossen — `ChannelFidelitySMS.svelte`
und `ChannelPreviewCard.svelte` wurden nie von einer Route importiert (nur über den
Organisms-Barrel `organisms/index.ts` erreichbar), die Trip-Editor-Route rendert
tatsächlich `WeatherV2MailPreview.svelte` mit einer eigenen, unverändert gebliebenen
SMS-Simulation. Entscheidungspunkt 2 dieses ADR griff damit für die Briefing-SMS-
Editor-Vorschau erst ab #923b tatsächlich live — nicht bereits ab #923. #923b schließt
den Endpoint an `WeatherV2MailPreview.svelte` an (`context==='route'`) und löscht die
fünf toten Komponenten (`ChannelFidelitySMS.svelte`, `ChannelPreviewCard.svelte`,
`ChannelPreviewBlock.svelte`, `ChannelFidelityEmail.svelte`, `ChannelFidelityBubble.svelte`).
Für den Ortsvergleich-Editor (`context==='vergleich'`) bleibt die SMS-Kachel bewusst
ausgeblendet statt falsch zu simulieren — eine Mehrort-SMS-Vorschau ist ein eigenes,
noch unspezifiziertes Vorhaben. Spec: `docs/specs/modules/fix_923b_wire_live_sms_preview.md`.
