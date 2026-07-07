# Context + Analyse: #1068 Level-Datenmodell + Anzeige im Account

## Request Summary
Slice 1 aus Epic #1067: neues Feld `Tier` (`free`/`standard`/`premium`, Default `free`) auf dem
User-Modell, Ausgabe in `GET /api/auth/profile`, Anzeige als Badge im Account-Bereich. Reine
Anzeige — kein Enforcement, kein Upgrade-Mechanismus (kommt in Slice 2-4).

Die Epic-Spec `docs/specs/modules/epic_user_tiers_overview.md` hat die Systemrecherche für alle
4 Slices bereits vollständig erledigt. Dieser Context-Schritt bestätigt die konkreten Code-Stellen
für Slice 1 und legt die offenen Detailfragen fest.

## Related Files

| File | Relevanz |
|------|----------|
| `internal/model/user.go:10-22` | `User`-Struct — neues Feld `Tier string \`json:"tier,omitempty"\`` |
| `internal/handler/auth.go:363-373` | `profileResponse`-Struct — neues Feld `Tier` |
| `internal/handler/auth.go:385-410` | `toProfileResponse()` — Default-Fallback `free` wenn `u.Tier == ""` |
| `internal/store/user.go:48-79` | `LoadUser`/`SaveUser` — reines `json.Unmarshal`/`Marshal`, kein Read-Modify-Write-Layer nötig, neues Feld reiht sich automatisch ein |
| `frontend/src/routes/account/+page.svelte:567-606` | Card "Dein Account" — neues Badge neben den Benachrichtigungs-Badges |
| `frontend/src/routes/account/+page.server.ts:19` | lädt `profile` per `fetch(...).then(r => r.json())` — **kein typisiertes Interface**, `data.profile` ist implizit `any` |
| `frontend/src/lib/types.ts` | **kein bestehendes `UserProfile`/`Profile`-Interface gefunden** — `ActivityProfile` (Zeile 109) ist ein anderes Konzept (Trip-Vorlage, nicht User-Level). Neuer Typ-Export `UserTier` hier sinnvoll für Wiederverwendung in Slice 2-4 (Channel-Gating, Badge-Komponente) |

## Existing Patterns
- Andere optionale User-Felder (`MailTo`, `SmsTo`, `TelegramChatID`) nutzen `omitempty` + leerer
  String als "nicht gesetzt" — exakt das Muster, das Tier für "Default free" braucht.
- Badge-Rendering im Account: `<Badge variant="secondary">Label: Wert</Badge>`, bedingt auf
  Vorhandensein (`{#if data.profile.mail_to}`) — Tier-Badge ist immer vorhanden (jeder Nutzer hat
  einen Tier-Wert, auch wenn nur "free"), daher unbedingtes Rendering statt `{#if}`.
- `profileResponse`/`toProfileResponse()` ist die einzige Stelle, die `model.User` in die
  API-Response übersetzt — keine zweite Mapping-Stelle vorhanden.

## Dependencies
- Upstream: `model.User` wird von `Store.LoadUser`/`SaveUser` (JSON-Roundtrip) sowie von
  `src/app/loader.py:818-825` (Python liest dieselbe `user.json` als Dict) verwendet.
- Downstream: `GET /api/auth/profile` wird von mehreren Frontend-Stellen konsumiert
  (`account/+page.server.ts`, `CompareTabs.svelte`, `WeatherMetricsTab.svelte`) — die sind lose
  typisiert (`{ mail_to?: string; ... }`), das neue `tier`-Feld bricht dort nichts (additiv).

## Existing Specs
- `docs/specs/modules/epic_user_tiers_overview.md` — Epic-Übersicht, Slice-Schnitt, PO-Entscheidungen
  (Default-Level bestätigt: "free" für neue UND bestehende Nutzer, Feld fehlt im `user.json` → wird
  als "free" behandelt, kein Zwangs-Rewrite).

## Risks & Considerations
- **Zero-Value-Ambiguity:** Go's `omitempty` unterscheidet nicht zwischen "Feld war nie gesetzt"
  und "Feld ist explizit leerer String" — für dieses Slice irrelevant, da beide Fälle laut
  PO-Entscheidung identisch als "free" behandelt werden sollen.
  Default-Fallback gehört in `toProfileResponse()` (Response-Zeitpunkt), NICHT beim Schreiben in
  `user.go`/`store.go` — sonst würde jeder Save eines Bestandsnutzers implizit `"free"` in die Datei
  schreiben, was zwar harmlos aber unnötig invasiv wäre (Prinzip: nur ändern was nötig ist).
- **Kein bestehendes Frontend-Interface für `Profile`** — `data.profile` bleibt `any` (aus
  `.json()`), daher ist die "Änderung" in `types.ts` ein reiner Zusatz-Export
  (`export type UserTier = 'free' | 'standard' | 'premium';`), keine Änderung an einem bestehenden
  Interface. Für die Account-Seite selbst reicht `data.profile.tier` (any) ohne Typwechsel.
- **Anzeige-Label:** Rohwerte `free`/`standard`/`premium` sind keine für Endnutzer gedachten
  Labels — Badge sollte deutsche Labels zeigen ("Free" / "Standard" / "Premium" reichen als
  Eigennamen, ggf. mit Zusatz-Text ist Overkill für Slice 1 laut Epic-Scope "Badge").
- **Kein Enforcement in diesem Slice:** Channel-Gating (Slice 2) und Alert-Frequenz (Slice 3)
  bleiben bewusst außerhalb des Scopes — dieses Slice ist reine Anzeige, keine
  Sicherheitsgrenze. Kein Cross-User-Risiko, da `Tier` nur aus dem bereits `user_id`-gescopten
  `GetProfileHandler` gelesen wird (`middleware.UserIDFromContext`).

## Offene Detailfrage für Spec-Phase
- Exaktes Badge-Label/Styling (z.B. `variant="secondary"` wie die anderen Badges, oder eigene
  Farbe pro Level?) — wird in `/30-write-spec` als AC festgelegt, PO-Freigabe erforderlich.
