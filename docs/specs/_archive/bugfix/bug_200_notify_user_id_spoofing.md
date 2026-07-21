---
entity_id: bug_200_notify_user_id_spoofing
type: bugfix
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [bugfix, security, auth, proxy]
---

<!-- Bug #200 (folge von #198) — appendUserID erlaubt user_id-Spoofing -->

# Bug #200 — Go-Proxy `appendUserID` erlaubt user_id-Spoofing

## Approval

- [ ] Approved

## Purpose

`internal/handler/proxy.go::appendUserID()` hängt die Session-`user_id` an die vom Client gesendete Query-String an, statt sie zu ersetzen. Ein eingeloggter User Alice kann `?user_id=bob` mitsenden — Python sieht `?user_id=bob&user_id=alice`. FastAPI verarbeitet typischerweise den ersten Wert → Alice triggert Operationen auf Bob's Profil (z. B. Channel-Test, Trip-Load).

Fix: `appendUserID()` entfernt zuerst alle existierenden `user_id`-Parameter aus der Query, dann hängt den authentifizierten ran.

## Source

- **File:** `internal/handler/proxy.go` — Funktion `appendUserID()`
- **File:** `internal/handler/proxy_test.go` (neu oder erweitert) — Unit-Test

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `net/url` Go stdlib | Helper für Query-Parsing |
| `internal/middleware.UserIDFromContext` | bestehend | liefert authentifizierten user_id |

## Implementation Details

Aktuelle Funktion:
```go
func appendUserID(rawQuery, userID string) string {
    if userID == "" {
        return rawQuery
    }
    if rawQuery == "" {
        return "user_id=" + userID
    }
    return rawQuery + "&user_id=" + userID
}
```

Neue Funktion:
```go
func appendUserID(rawQuery, userID string) string {
    if userID == "" {
        return rawQuery
    }
    // Parse + remove any user_id submitted by the client (defense against spoofing)
    values, err := url.ParseQuery(rawQuery)
    if err != nil {
        // Malformed query — drop it entirely, keep only authenticated user_id
        return "user_id=" + userID
    }
    values.Del("user_id")
    values.Set("user_id", userID)
    return values.Encode()
}
```

## Acceptance Criteria

- **AC-1:** Given rawQuery=`""`, userID=`"alice"` / When `appendUserID()` läuft / Then Resultat enthält `user_id=alice` und keine weiteren Parameter
- **AC-2:** Given rawQuery=`"foo=bar"`, userID=`"alice"` / When `appendUserID()` läuft / Then Resultat enthält `foo=bar` UND `user_id=alice` (Reihenfolge egal)
- **AC-3:** Given rawQuery=`"user_id=bob"`, userID=`"alice"` / When `appendUserID()` läuft / Then Resultat enthält **nur** `user_id=alice` (kein `user_id=bob`) — Anti-Spoofing
- **AC-4:** Given rawQuery=`"user_id=bob&other=x&user_id=eve"`, userID=`"alice"` / When `appendUserID()` läuft / Then Resultat enthält `user_id=alice` und `other=x`, **keine** `bob`/`eve`
- **AC-5:** Given userID=`""` (kein authentifizierter User) / When `appendUserID()` läuft / Then Resultat = rawQuery unverändert (keine Auth → kein Override)

## Expected Behavior

- **Input:** raw query string + authenticated user_id from session context
- **Output:** Bereinigte Query mit garantiert genau einem `user_id=` (dem authentifizierten) oder unverändert wenn keine Auth
- **Side effects:** Keine — pure function

## Known Limitations

- `url.ParseQuery` ist tolerant — bei Malformed-Query droppen wir die ganze Query und behalten nur das authentifizierte `user_id`. Konservativer Fail-Safe.
- Frontend-Code wird nicht angepasst — er sendet ohnehin kein `user_id` mit.

## Changelog

- 2026-05-11: Initial spec — Bug #200 (Folgebug aus #198-Analyse)
