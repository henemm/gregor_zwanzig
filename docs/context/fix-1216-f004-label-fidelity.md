# Context + Analysis: fix-1216-f004-label-fidelity (#1216 F004)

## Request Summary
Der Mail-**Betreff** amtlicher Warnungen zeigt für zwei Fälle nur das saubere
Typ-Wort und verliert dabei Detail, das im Label steckt: (1) **Massiv-Sperren**
(`access_ban`) — welches Massiv gesperrt ist; (2) **Vigilance** — z. B. „Extreme
Hitze" statt nur „Hitze". PO-Entscheidung: **pragmatisch in Code** lösen (keine
neue Design-Vorlage), Darstellung wähle ich; Betreff + Body sollen das Detail
zeigen. Mail-Body zeigt das volle Label bereits.

## Wurzel (verifiziert)
| Fakt | Quelle |
|------|--------|
| Massiv-Label = `"Zugang gesperrt — {name}"` (3 Varianten: eingeschränkt/gesperrt/gesperrt (total)) | `src/services/official_alerts/massif_closure.py:61-67` |
| Vigilance-Mapping: `"6": ("extreme_heat", "Extreme Hitze")`, `"3": ("thunderstorm","Gewitter")` | `src/services/official_alerts/vigilance.py:48-52` |
| Sauberes Typ-Wort im Betreff: `_HAZARD_DISPLAY["access_ban"]="Zugang gesperrt"`, `extreme_heat="Hitze"` | `src/output/renderers/alert/official_alerts.py:42-50` |
| Betreff baut Typ via `_typ_tag` → `_hazard_display()[0]` (Typ-Wort, **nicht** Label) | `official_alerts.py:314-318, 321-334` |
| Unbekannte Hazards (z. B. `wildfire_risk`) fallen in `_hazard_display` auf `alert.label` zurück → zeigen schon volles Label | `official_alerts.py:269-276` |
| SMS nutzt Kurzcode (`_hazard_display()[1]`, z. B. „ZG"), NICHT den Betreff → SMS-Länge unberührt | `official_alerts.py:475-500` |
| HTML-Notice/Plain zeigen `alert.label` voll → Body bereits detailtreu | `official_alerts.py:104-124, 218-225` |
| `OfficialAlert` hat kein separates Massiv-Feld — Detail steckt im `label` (nach „— "); `dedup_id`=Massiv-ID stabil | `src/services/official_alerts/models.py:15-33` |

## Related Files
| Datei | Änderung |
|------|----------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY — `_typ_tag` (Betreff-Typ) detailtreu; ggf. Chip/`affected_chips`-Quelle prüfen |
| Alert-Renderer-Testsuite (`tests/…/test_*official_alert*`) | MODIFY/CREATE — Betreff-Fidelity-Tests |

## Analysis

### Type
Bug/Fidelity-Fix (Betreff verliert vorhandenes Detail)

### Technischer Ansatz (Empfehlung)
`_typ_tag` so ändern, dass es **das Label bevorzugt, wenn es mehr trägt als das
Typ-Wort**, sonst unverändert das Typ-Wort (Kompaktheit/Konsistenz der sauberen
Fälle bleibt). Generische, regressionssichere Regel:
- Ausgangsbasis bleibt `_hazard_display()[0]` (Typ-Wort `w`).
- Ist `alert.label` „reicher" als `w` (Label ≠ `w` und beginnt mit `w` **oder**
  ist eine Vigilance-Bezeichnung), verwende `alert.label` statt `w` im Typ-Tag.
  - `access_ban`: `"Zugang gesperrt — Rotwand-Massiv"` → Typ-Tag zeigt das Massiv.
  - `extreme_heat` (Vigilance): `"Extreme Hitze"` → statt „Hitze".
- Wochentag-Suffix `(Tag)` bleibt unverändert.
- **Invariante:** Fälle, in denen `label == w` (oder GeoSphere-Standard „Hitze"),
  ergeben **identischen** Betreff wie heute (keine Regression).

**Betreff-Platzierung:** Detail wandert in den **Typ-Tag** →
`[KHW …] <Reichweite> · ROT Zugang gesperrt — Rotwand-Massiv (Sa)`. Technisch
sauberer als das Detail in `scope_label` (= Reichweite/„welche Orte") zu mischen.
Die PO-Vorschau zeigte das Massiv prominent im Betreff (Position illustrativ) →
exakte Platzierung in ACs bestätigen lassen.

**Betreff-Länge:** Es gibt einen Truncation-Helfer (`official_alerts.py:462`);
prüfen, dass längere Typ-Tags korrekt gekürzt werden (kein Mid-Wort-Schnitt).

### Scope
- Files: 2 (Renderer + Test) · LoC: ~+40/−10 · Risk: MEDIUM (Mail-Betreff, sicherheitsrelevanter Massiv-Name; saubere Fälle invariant)

### Dependencies
- Upstream: `_hazard_display`, `alert.label`/`dedup_id`. Downstream: Trip- und
  Compare-Betreff (`notification_service.py:482,575`) — beide über dieselbe Funktion.

### Gates (wichtig)
- `official_alerts.py` = Mail-Inhalt → **renderer_mail_gate** + echte Test-Mail
  vor Commit (alert/*.py triggert Radar-Validator No-Op → Nachweis via echter
  Staging-Mail nötig, s. [[reference_renderer_mailgate_log_perm_trap]], [[reference_three_briefing_renderers_and_testmail_send]]).

### Open Questions (für Spec/ACs)
- [ ] Betreff-Platzierung: Detail im Typ-Tag (`… · ROT Zugang gesperrt — Rotwand-Massiv (Sa)`) — bestätigen.
- [ ] Vigilance „Extreme Hitze" im Betreff mitnehmen (statt „Hitze") — bestätigen; oder nur Massiv-Fall im Scope?
- [ ] Bündelungs-Betreff mit mehreren Warnungen: Detail nur bei access_ban/Vigilance, Rest kompakt?
