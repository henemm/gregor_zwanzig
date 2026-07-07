# Context: Tiers-2 — Channel-Gating nach Nutzerlevel (Issue #1069)

## Request Summary
SMS darf nur an Nutzer mit Level Standard/Premium versendet werden — serverseitig
durchgesetzt (nicht nur im Frontend), da `trip_report_scheduler.py` das
`send_sms`-Flag heute ungeprüft umsetzt. Frontend zeigt bei Level-bedingter Sperre
"ab Standard verfügbar" statt "Handynummer fehlt". Premium-SMS (Garmin inReach)
nur als deaktivierter Menüpunkt-Slot, kein Funktionscode.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/model/user.go:22` | `Tier` Feld (aus Slice 1 #1068), bereits vorhanden |
| `internal/handler/auth.go:361-413` | `profileResponse` + `toProfileResponse` — Default-Fallback "free" bereits implementiert |
| `src/services/trip_report_scheduler.py:623,835` | Zwei Enforcement-Punkte: `send_sms=config is not None and config.send_sms` — hier fehlt die Tier-Prüfung |
| `src/app/config.py:197-230` | Pattern für Python-seitiges Lesen von `data/users/<id>/user.json` als rohes Dict (kein Python-`User`-Objekt mit Tier) — Vorbild für Tier-Lookup |
| `src/app/models.py:717` | `ReportConfig.send_sms: bool` — rein persistiertes Nutzer-Flag, keine Tier-Kenntnis |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte:80-93,405-419` | `availableChannels`-Derivation (aktuell nur Kontaktdaten-Check) + Hint-Pattern ("Handynummer fehlt") — Vorlage für Level-Hint |
| `frontend/src/lib/types.ts:499-501` | `UserTier = 'free' \| 'standard' \| 'premium'` bereits gespiegelt |
| `frontend/src/routes/account/+page.svelte:43-50,585-587` | Tier-Anzeige-Pattern aus Slice 1 |

## Existing Patterns

- **Cross-Language-Spiegelung statt Code-Sharing:** Go ist Source of Truth für `Tier`
  (`internal/model/user.go`), Frontend spiegelt den Typ in TS (`types.ts:499-501`) mit
  Kommentar-Verweis auf die Go-Quelle. Kein gemeinsamer Code zwischen Go/Python/TS —
  etablierte Konvention in diesem Projekt.
- **Python liest `user.json` roh als Dict**, nicht über ein eigenes `User`-Objekt
  (`config.py:213` `json.loads(profile_path.read_text())`). Für den Tier-Lookup im
  Scheduler ist das der nächstliegende Ansatz — kein neues Python-User-Modell nötig.
- **Frontend-Gating-UI existiert bereits 1:1 fürs Muster** "Checkbox disabled + Hinweistext
  darunter" (`channel-sms-hint`, `channel-telegram-hint`). Level-Gating reiht sich hier ein,
  keine neue UI-Mechanik.

## Dependencies

- **Upstream:** `Tier`-Feld aus Slice 1 (#1068, bereits live) — Default "free" bei fehlendem
  Feld, an zwei Stellen bereits konsistent behandelt (Go `toProfileResponse`, künftig auch
  Python-Lookup).
- **Downstream:** Slice 3 (#1070, Alert-/Update-Frequenz) wird vermutlich denselben
  Tier-Lookup-Mechanismus (Python, `data/users/<id>/user.json`) wiederverwenden.

## Existing Specs

- `docs/specs/modules/epic_user_tiers_overview.md` — Epic-Übersicht, enthält bereits
  detaillierten Vorschlag für Slice 2 (Dateien, ~150-200 LoC, Premium-SMS-Slot-Anforderung).
- `docs/specs/modules/issue_1068_tier_model_display.md` — Slice-1-Spec (Referenz für
  Read-Modify-Write-Konvention beim Tier-Feld).

## Risks & Considerations

- **Wo lebt die Tier→Channel-Tabelle?** Das Epic nennt `internal/model/` als betroffenes
  System für eine neue Tier→Channel-Tabelle, aber die tatsächliche Durchsetzung passiert
  in Python (`trip_report_scheduler.py`), das keinen Go-Code importieren kann. Empfehlung:
  Go bekommt die Tabelle als Source of Truth (`internal/model/tier.go`) und reichert
  `profileResponse` um ein Feld an (z.B. `sms_allowed bool`), damit das Frontend die
  Tier→Channel-Logik NICHT selbst dupliziert. Python bekommt eine eigene, kleine
  gespiegelte Konstante (analog zum bestehenden Tier-Typ-Spiegelungs-Pattern) für den
  Enforcement-Punkt im Scheduler. Das hält die Duplizierung auf das in diesem Projekt
  bereits etablierte Maß (2 Stellen: Go + Python) statt 3 (zusätzlich Frontend).
- **Reihenfolge der Hint-Texte:** Wenn sowohl Handynummer fehlt ALS AUCH Tier zu niedrig ist,
  muss der Level-Hint Vorrang haben (Nummer eintragen würde nichts ändern). Wird als AC in
  der Spec festgehalten.
- **Kein Python-`User`-Objekt mit Tier vorhanden** — Lookup erfolgt wie in `config.py` via
  direktem JSON-Read von `data/users/<user_id>/user.json`, kein neues Objektmodell.
- **Premium-SMS-Slot** ist reine UI (deaktivierte Menüzeile + "bald verfügbar"-Hinweis),
  keine Funktionslogik — Kanal existiert serverseitig nicht.
- **Scope-Grenze:** Slice 3 (Alert-Frequenz-Tageszähler) ist explizit NICHT Teil dieses
  Slices.
