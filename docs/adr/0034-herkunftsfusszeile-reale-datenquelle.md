# ADR-0034: Herkunfts-Fußzeile zeigt die reale Datenquelle statt Renderer-Pfad + Commit-Hash

- **Status:** Akzeptiert
- **Datum:** 2026-07-23
- **Bezug:** Ersetzt #1241 (nie als ADR dokumentiert). Bundle
  `bundle:G-mail-darstellung`, Issue #1338 (Befund 4a). Spec:
  `docs/specs/modules/warnmail_official_alert_display.md` (AC-5). Fallback-Regel
  siehe ADR-0029 (Open-Meteo als Standard-Provider).

## Kontext

Issue #1241 führte eine zweizeilige Herkunfts-Fußzeile (`build_origin_footer`,
`src/output/renderers/email/helpers.py`) für alle Mail-Renderer ein. Zeile 2
zeigte `f"{renderer_name}{variant} · {_DEPLOYED_COMMIT}"` — den internen
Renderer-Dateipfad (z.B. `alert/render.py`, `email/html.py`) plus den
kurzen Git-Commit-Hash des Laufzeit-Checkouts. Diese Festlegung stand nur in
Code-Kommentaren/der #1241-Umsetzung, nie als ADR.

Für Nutzer ist ein interner Renderer-Pfad + Commit-Hash kein fachlicher Wert —
er beantwortet nicht die eigentlich relevante Frage „woher stammt dieses
Wetter/diese Warnung". Bei fehlendem `.git`-Checkout (z.B. in bestimmten
Deploy-Umgebungen) fiel die Zeile zusätzlich auf den Platzhalter `"unknown"`
zurück — ein bedeutungsloser Wert in einer nutzerorientierten Fußzeile.

## Entscheidung

Zeile 2 der Herkunfts-Fußzeile zeigt die **tatsächliche Datenquelle**, vom
Aufrufer bestimmt und an `build_origin_footer(..., source=...)` durchgereicht:

| Mail-Typ | Quelle in Zeile 2 |
|---|---|
| trip-briefing (full/compact), plain | `segments[0].provider` |
| official-alert (Standalone + eingebettet) | `source_label` (nach ADR-0033-Nachbarfix #1251 ggf. mehrere Quellen, komma-separiert) |
| radar-alert (Onset) | `OnsetEvent.source_label` (z.B. „Radar (DWD)") |
| deviation-alert (Trip + Compare) | fester Fallback `"Open-Meteo"` (ADR-0029) |
| compare (Ortsvergleich-Mail-Fuß) | fester Fallback `"Open-Meteo"` (ADR-0029) |

Niemals `"unknown"`, niemals ein interner `.py`-Pfad, niemals ein reiner
Commit-Hash als alleiniger Inhalt von Zeile 2. `_deployed_commit()` bleibt als
Hilfsfunktion bestehen (u.a. für Tests), wird aber nicht mehr in Zeile 2
verbaut.

## Verworfene Alternativen

- **Zeile 2 ganz entfernen** — verliert den fachlichen Mehrwert einer
  Herkunftsangabe komplett, statt ihn nutzerorientiert neu zu befüllen.
- **Sofortige `AlertMessage`-Modelländerung für echtes per-Event-Provider-
  Tracking bei Abweichungs-Alarmen** — sprengt den Affected-Files-Rahmen dieses
  Bündels (reine Renderer-/Service-Ebene ohne `alert/model.py`); bleibt
  dokumentierte Folgearbeit (s. Known Limitations der Spec).

## Konsequenzen

- **Positiv:** Jede Mail-Fußzeile beantwortet „woher kommt diese Information"
  mit einem fachlichen Wert statt eines internen Implementierungsdetails.
- **Negativ / Preis:** Für deviation-alert (Trip + Compare) und die
  Ortsvergleich-Mail ist der Fallback `"Open-Meteo"` korrekt, solange ADR-0029
  gilt (ein einziger Live-Standard-Provider) — er wird falsch, sobald ein
  zweiter Live-Provider aktiv würde. Der Commit-Hash zur Build-Identifikation
  ist aus der nutzerseitigen Fußzeile verschwunden (bleibt intern über
  `_deployed_commit()`/Deploy-Logs verfügbar).
- **Folgepflichten:** Echtes per-Event-Provider-Tracking für Abweichungs-Alarme
  erfordert eine `AlertMessage`-Modelländerung (additives Feld analog
  `location_label`/`cooldown_display`) — eigenes Issue, nicht Teil dieses ADRs.
