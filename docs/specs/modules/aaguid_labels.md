---
entity_id: aaguid_labels
type: module
created: 2026-05-30
updated: 2026-05-30
status: active
version: "1.0"
tags: [go, sveltekit, auth, webauthn, passkey, aaguid, ux]
---

<!-- Issue #468 — AAGUID-Labels in der Passkey-Liste -->

# AAGUID-Labels in der Passkey-Liste

## Approval

- [x] Approved

## Purpose

`aaguidToName` übersetzt die 16-Byte-AAGUID eines WebAuthn-Credentials in einen menschenlesbaren Geräte- bzw. Herstellernamen (z.B. „iCloud Keychain", „YubiKey 5 NFC", „Windows Hello"). Damit zeigt die Account-Seite nicht nur das vom User vergebene Label, sondern auch den Authenticator-Typ — das hilft beim Verwalten mehrerer Passkeys auf unterschiedlichen Geräten, ohne dass der User selbst sorgfältig benennen muss.

## Source

- **File:** `internal/handler/aaguid.go` **(NEU)** — statische AAGUID-Map (~25 Einträge) + `aaguidToName([]byte) string`
- **Identifier:** `aaguidToName`

### Weitere betroffene Dateien

- **File:** `internal/handler/aaguid_test.go` **(NEU)** — Unit-Tests für `aaguidToName`
- **File:** `internal/handler/auth.go` (ERWEITERT) — `passkeyProfileEntry` erhält Feld `AuthenticatorName string`; `toProfileResponse()` befüllt es via `aaguidToName`
- **File:** `frontend/src/routes/account/+page.svelte` (ERWEITERT) — `PasskeyEntry`-Typ + kombinierte Anzeige-Logik

> **Schicht-Hinweis:** Die AAGUID-Lookup-Logik liegt ausschliesslich in der **Go-API** (`internal/handler/`). Das SvelteKit-Frontend empfängt den aufgelösten Namen als String-Feld `authenticator_name` in der Profile-Response — kein Lookup im Browser. Bestätigung per Grep: `passkeyProfileEntry` ist in `internal/handler/auth.go` definiert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/user.go` | go package | `WebAuthnCredential.Authenticator.AAGUID []byte` — Quelle der 16-Byte-AAGUID |
| `internal/handler/auth.go` | go package | `passkeyProfileEntry` — wird um `AuthenticatorName string \`json:"authenticator_name,omitempty"\`` erweitert; `toProfileResponse()` ruft `aaguidToName` auf |
| `fmt` | go stdlib | `fmt.Sprintf` für UUID-String-Formatierung der AAGUID-Bytes |
| `passkey_webauthn` Spec | spec | Definiert `WebAuthnCredential`-Struktur mit `Authenticator.AAGUID`-Feld, das diese Spec liest |

## Implementation Details

### Step 1: `aaguidToName` in `internal/handler/aaguid.go` (NEU, ~55 LoC)

```go
package handler

import "fmt"

// aaguidMap bildet bekannte AAGUID-UUID-Strings auf Klartextnamen ab.
// Quelle: https://passkeydeveloper.github.io/passkey-authenticator-aaguids/aaguids.json
var aaguidMap = map[string]string{
    "fbfc3007-154e-4ecc-8cfb-6ef08c534b35": "iCloud Keychain",
    "08987058-cadc-4b81-b6e1-30de50dcbe96": "Windows Hello",
    "9ddd1817-af5a-4672-a2b9-3e3dd95000a9": "Windows Hello",
    "6028b017-b1d4-4c02-b4b3-afcdafc96bb2": "Windows Hello",
    "ee882879-721c-4913-9775-3dfcce97072a": "Google Password Manager",
    "2fc0579f-8113-47ea-b116-bb5a8db9202a": "YubiKey 5 NFC",
    "cb69481e-8ff7-4039-93ec-0a2729a154a8": "YubiKey 5",
    "c1f9a0bc-1dd2-404a-b27f-8e29047a43fd": "YubiKey 5C NFC",
    "d548826e-79b4-db40-a3d8-11116f7e8349": "Bitwarden",
    "bada5566-a7aa-401f-bd96-45619a55120d": "1Password",
    "53414d53-554e-4700-0000-000000000000": "Samsung Pass",
    "b93fd961-f2e6-462f-b122-82002247de78": "Android Fingerprint / Screen Lock",
    "6e9ac0b4-c626-4e0a-869f-6e3bf5e72291": "KeePassXC",
    "66a0ccb3-bd6a-191f-ee06-e375c50b9846": "Thales Bio iOS SDK",
    "17290f1e-c212-34d0-1423-365d729f09d9": "Thales PIN Android SDK",
    "adce0002-35bc-c60a-648b-0b25f1f05503": "Chrome on Mac",
    "08987058-cadc-4b81-b6e1-30de50dcbe96": "Windows Hello Hardware",
    "9f77e279-a6e2-4d58-b700-31e5943c6a98": "Yubico Security Key NFC",
    "149a2021-3ef5-41e4-8ccc-e6f8-c3c1-4d5d": "Yubico Security Key C NFC",
    "2ffd6452-01da-471f-821b-ea4bf6c8676a": "Feitian ePass FIDO2",
    "12ded745-4bed-47d4-abaa-e713f51d6393": "Feitian BioPass FIDO2 Pro",
    "87dbc5a1-4c94-4dc8-8a47-97d800fd1f3c": "Enpass",
    "39a5647e-1853-446c-a1f6-a79bae9f5bc7": "IDmelon",
    "820d89ed-d65a-409e-85cb-f73f0578f82a": "ID-One Card",
}

// aaguidToName gibt den Klartextnamen eines Authenticators zurück.
// Bei Zero-AAGUID, unbekannter AAGUID oder falscher Länge wird "" zurückgegeben.
func aaguidToName(b []byte) string {
    if len(b) != 16 {
        return ""
    }
    // Zero-AAGUID (alle Bytes 0x00) bedeutet: kein Authenticator-Name bekannt
    allZero := true
    for _, v := range b {
        if v != 0 {
            allZero = false
            break
        }
    }
    if allZero {
        return ""
    }
    uuid := fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
        b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
    return aaguidMap[uuid] // "" wenn nicht gefunden
}
```

### Step 2: `passkeyProfileEntry` erweitern (`internal/handler/auth.go`, +3 LoC)

Das bestehende Struct (aus der `passkey_webauthn`-Spec, Step 6) erhält ein weiteres Feld:

```go
type passkeyProfileEntry struct {
    ID                string    `json:"id"`
    Label             string    `json:"label,omitempty"`
    AuthenticatorName string    `json:"authenticator_name,omitempty"` // NEU
    CreatedAt         time.Time `json:"created_at"`
    LastUsedAt        time.Time `json:"last_used_at,omitempty"`
}
```

In `toProfileResponse()` (oder entsprechender Inline-Befüllung):

```go
entry := passkeyProfileEntry{
    ID:                base64.URLEncoding.EncodeToString(pc.ID),
    Label:             pc.Label,
    AuthenticatorName: aaguidToName(pc.Authenticator.AAGUID), // NEU
    CreatedAt:         pc.CreatedAt,
    LastUsedAt:        pc.LastUsedAt,
}
```

Das `omitempty`-Tag sorgt dafür, dass bei Zero-AAGUID oder unbekannter AAGUID das Feld in der JSON-Response schlicht fehlt — keine Breaking Change für Clients, die das Feld nicht kennen.

### Step 3: Frontend-Anzeige (`frontend/src/routes/account/+page.svelte`, ~8 LoC Änderung)

Typ-Erweiterung:

```typescript
type PasskeyEntry = {
    id: string;
    label?: string;
    authenticator_name?: string; // NEU
    created_at: string;
    last_used_at?: string;
};
```

Anzeige-Logik (ersetzt bisherigen `pk.label || 'Unbenanntes Gerät'`):

```svelte
<strong>
    {[pk.authenticator_name, pk.label].filter(Boolean).join(' · ') || 'Unbenanntes Gerät'}
</strong>
```

Damit zeigt die Liste z.B.:
- „iCloud Keychain · Mein MacBook" (beide Felder gesetzt)
- „iCloud Keychain" (nur AAGUID bekannt, kein Label vergeben)
- „Mein MacBook" (AAGUID unbekannt, Label vergeben)
- „Unbenanntes Gerät" (AAGUID unbekannt, kein Label)

### Step 4: Tests (`internal/handler/aaguid_test.go` NEU, ~24 LoC)

```go
package handler

import (
    "testing"
    "encoding/hex"
)

func TestAaguidToName(t *testing.T) {
    // Bekannte AAGUID → richtiger Name
    iCloudAAGUID, _ := hex.DecodeString("fbfc3007154e4ecc8cfb6ef08c534b35")
    if got := aaguidToName(iCloudAAGUID); got != "iCloud Keychain" {
        t.Errorf("iCloud: got %q", got)
    }

    // Zero-AAGUID → ""
    zero := make([]byte, 16)
    if got := aaguidToName(zero); got != "" {
        t.Errorf("zero AAGUID: got %q", got)
    }

    // Unbekannte AAGUID → ""
    unknown := make([]byte, 16)
    unknown[0] = 0xAB
    if got := aaguidToName(unknown); got != "" {
        t.Errorf("unknown AAGUID: got %q", got)
    }

    // Falsche Länge → ""
    if got := aaguidToName([]byte{0x01, 0x02}); got != "" {
        t.Errorf("wrong length: got %q", got)
    }
}
```

## Expected Behavior

- **Input:** `[]byte` mit Länge 16 (AAGUID aus `WebAuthnCredential.Authenticator.AAGUID`)
- **Output:** Klartextname als `string` (z.B. `"iCloud Keychain"`) oder `""` bei Zero-AAGUID, unbekannter AAGUID oder falscher Länge
- **Side effects:** keine — pure Funktion, kein I/O, keine Persistenz-Änderung
- **Keine neue externe Dependency:** statische Map in Go, kein Netzwerk-Call, kein Datei-Lookup

### Gesamte Änderung in Zahlen

| Datei | LoC-Delta |
|-------|-----------|
| `internal/handler/aaguid.go` (NEU) | +55 |
| `internal/handler/aaguid_test.go` (NEU) | +24 |
| `internal/handler/auth.go` | +3 |
| `frontend/src/routes/account/+page.svelte` | +8 (netto, inkl. Typ) |
| **Gesamt** | **~90** (unter 250-Limit) |

## Acceptance Criteria

- **AC-1:** Given ein Passkey wurde mit einem iCloud-Keychain-Authenticator (AAGUID `fbfc3007-154e-4ecc-8cfb-6ef08c534b35`) registriert und der User öffnet die Account-Seite / When die Passkey-Liste geladen wird (GET `/api/auth/profile`) / Then enthält die JSON-Response das Feld `authenticator_name: "iCloud Keychain"` für diesen Eintrag und die Account-Seite zeigt den Text „iCloud Keychain" sichtbar in der Passkey-Zeile an
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Passkey wurde mit einem Software-Authenticator ohne hinterlegte AAGUID registriert (Zero-AAGUID, alle Bytes 0x00) / When die Passkey-Liste geladen wird / Then fehlt das Feld `authenticator_name` in der JSON-Response vollständig (nicht `null`, nicht `""`), und die Account-Seite zeigt für diesen Passkey nur das User-Label oder „Unbenanntes Gerät" an — ohne Trennzeichen oder leeres Präfix
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Passkey hat sowohl eine bekannte AAGUID (z.B. „Windows Hello") als auch ein vom User vergebenes Label (z.B. „Büro-PC") / When die Account-Seite die Passkey-Zeile rendert / Then zeigt die Zeile exakt „Windows Hello · Büro-PC" an — Authenticator-Name zuerst, Label nach dem Trennzeichen ` · `
  - Test: (populated after /tdd-red)

- **AC-4:** Given die Funktion `aaguidToName` wird mit einem Byte-Slice der Länge ungleich 16 aufgerufen (z.B. leer, 15 Bytes, 17 Bytes) / When die Funktion ausgeführt wird / Then gibt sie den leeren String `""` zurück ohne Panic oder sichtbaren Fehler — bestehende Passkey-Liste bleibt vollständig darstellbar
  - Test: (populated after /tdd-red)

- **AC-5:** Given bestehende Passkeys, die vor diesem Feature registriert wurden (d.h. ihr `authenticator_name`-Feld existiert in gespeicherten JSON-Dateien nicht) / When `/api/auth/profile` aufgerufen wird / Then ist die Response valides JSON ohne Fehler, fehlende `authenticator_name`-Felder werden durch `omitempty` weggelassen, und die Frontend-Passkey-Liste zeigt alle bestehenden Passkeys korrekt an (keine leeren Labels, kein Rendering-Fehler)
  - Test: (populated after /tdd-red)

## Known Limitations

- **Statische Map:** Die AAGUID-Liste ist zur Compile-Zeit eingefroren. Neue Authenticators werden erst mit dem nächsten Code-Deploy erkannt. Für ein internes Tool mit stabilem Authenticator-Ökosystem akzeptabel; ein dynamischer Download (z.B. von `passkeydeveloper.github.io`) würde Netzwerk-Abhängigkeit und Caching-Komplexität einführen.
- **~25 Einträge:** Die Map deckt die verbreiteten Consumer-Authenticators ab (Apple, Google, Microsoft, YubiKey, Bitwarden, 1Password). Weniger gebräuchliche Hardware-Keys (Feitian, Kensington, etc.) liefern leeren Namen — das ist für die Zielgruppe (Wanderer mit Consumer-Geräten) akzeptabel.
- **AAGUID-Formatierung via `fmt.Sprintf`:** Die Byte-zu-UUID-Konvertierung verwendet direkte Byte-Slicing-Arithmetik; kein `encoding/hex.EncodeToString` mit manuellem Bindestrich-Einfügen, da `fmt.Sprintf` mit `%x`-Verb sauberer und lesbarer ist.

## Changelog

- 2026-05-30: Initial spec — basierend auf Analyse zu Issue #468; Folge-Issue zu `passkey_webauthn` (#450)
