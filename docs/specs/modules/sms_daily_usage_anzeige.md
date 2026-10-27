---
entity_id: sms_daily_usage_anzeige
type: feature
created: 2026-09-25
updated: 2026-09-25
status: draft
workflow: feat-2153-s4b-sms-kontingent-anzeige
version: "1.0"
tags: [tiers, sms, premium-sms, account, epic-2138]
---

# SMS-/Premium-SMS-Tageskontingent im Account sichtbar (S4b — Anzeige)

## Approval

- [ ] Approved

## Purpose

S4a (live seit Commit fc6afefd, Issue #2412) hat das tägliche SMS-/Premium-SMS-Kontingent
durchgesetzt, aber ausschließlich als Durchsetzung + Log — der Nutzer selbst sieht seinen
Zählerstand nirgends. S4b macht diesen Zählerstand auf `/account` sichtbar ("3 von 10"), damit
ein Nutzer versteht, warum eine SMS ausbleibt, BEVOR er an die Kontingentgrenze stößt, statt es
erst aus einer ausbleibenden Nachricht zu erschließen. Reiner Lese-/Anzeige-Pfad ohne neue
Zähler-Semantik — S4a bleibt die alleinige Durchsetzungsinstanz. Sammel-Issue #2153, Einzel-Issue
#2412, Epic #2138 (Multi-User).

## Source

- **File (Python-Core, Lesefunktion):** `src/services/sms_daily_limit.py` — `get_daily_usage(user_id, now)` (neu)
- **File (Python-Core, Endpoint):** `api/routers/internal.py` — `GET /api/_internal/sms/daily-usage` (neu)
- **File (Go-API, Handler):** `internal/handler/sms_daily_usage.go` (neu) — `GetSmsDailyUsageHandler(cfg config.Config)`
- **File (Frontend):** `frontend/src/routes/account/+page.svelte`, `+page.server.ts` (MODIFY)

> **Schicht-Hinweis:** Vier Schichten sind betroffen — Python-Core (`src/services/`, `api/routers/`),
> Go-API (`internal/handler/`, `internal/router/`), Frontend (`frontend/src/routes/account/`).
> Kein Go-`internal/model`-Feld nötig: der Zähler bleibt Python-seitige Single Source of Truth
> und wird live geholt, nicht im `User`-Struct gespiegelt (analog `sms_daily_limit.py`, das
> ebenfalls keine Go-Persistenz hat).

## Estimated Scope

- **LoC:** ~140–170 (Produktionscode, ohne Tests und Doku-Nachträge)
- **Files:** 5 Produktionsdateien (`sms_daily_limit.py` MODIFY, `api/routers/internal.py` MODIFY,
  `internal/handler/sms_daily_usage.go` CREATE, `internal/router/router.go` MODIFY,
  `frontend/src/routes/account/+page.server.ts` + `+page.svelte` MODIFY) + 2 neue Testdateien
  (Python-Endpoint-Test, Go-Handler-Test) + ggf. 1 Frontend-Testdatei für die Sichtbarkeits-Logik
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/sms_daily_limit.py` (`_load`, `_zaehlerwert`, `_path`, `_today`, S4a) | module | Zähler-Schreibpfad und interne Helfer, auf denen die neue Lesefunktion aufsetzt |
| `src/services/user_tier.py` (`daily_sms_limit`, `daily_premium_sms_limit`, `SMS_ALARM_RESERVE`, `PREMIUM_SMS_ALARM_RESERVE`, `PREMIUM_SMS_REPLY_OVERSHOOT`) | module | Limit-/Reserve-Konstanten je Tier, Single Source of Truth für die DTO-Werte |
| `internal/handler/sms_verify.go` (`postSmsVerificationCode`, Zeilen 96-114) | pattern | Bauvorbild für Go→Python-Aufruf: `&http.Client{Timeout: ...}`, `X-GZ-Core-Auth` wird automatisch über `internal/coreauth/transport.go` angehängt (kein eigener Header-Code nötig) |
| `internal/coreauth/transport.go` | module | Globaler `RoundTripper` auf `http.DefaultTransport`, hängt `X-GZ-Core-Auth` an jeden Aufruf gegen `cfg.PythonCoreURL` — kein Zusatzcode im neuen Handler nötig |
| `internal/middleware` (`UserIDFromContext`) | module | Pflicht-Quelle der `user_id` im Go-Handler — niemals aus Query/Body übernehmen (Cross-User-Risiko) |
| `internal/model/tier.go` (`SmsAllowed`, `PremiumSmsAllowed`) | pattern | Bereits etabliertes Muster für Tier-abgeleitete Sichtbarkeits-Gates — hier NICHT genutzt, da die Sichtbarkeit je Kanal aus `limit > 0` der Python-DTO folgt, nicht aus einer zweiten Go-seitigen Ableitung |
| `frontend/src/routes/account/+page.server.ts` (Zeilen 21-36, `Promise.all(...).catch(() => null)`) | pattern | Bestehendes Fail-Soft-Muster für zusätzliche Account-Daten — neuer Fetch reiht sich hier ein |
| `frontend/src/lib/utils/premiumSmsLinkCodeHelpers` (`deriveLinkCodeExists`, Muster `shouldShowPremiumSmsLinkCard`) | pattern | Bauvorbild für eine reine, testbare Sichtbarkeits-Helferfunktion statt Inline-Bedingung in der Vorlage |
| `tests/tdd/test_sms_tageslimit.py` (`_kennung`, `_nutzer_anlegen`, `_zaehler_schreiben`, Zeilen 195-222) | pattern | Test-Helfer für Zähler-Fixtures und eindeutige `user_id` je Test (Mandantentrennungs-Pflicht) |
| `tests/test_sms_verification_code_endpoint.py` (Zeilen 80-108) | pattern | Vorbild für Python-Endpoint-Test mit `TestClient`, zwei Nutzern, `user_id` als Pflichtfeld |

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/sms_daily_limit.py` | MODIFY | Rollover-Logik aus `check_and_reserve` (Zeilen 172-176) in gemeinsamen Helfer `_tagesstand(data, today)` extrahiert; neue Funktion `get_daily_usage(user_id, now) -> dict` (reiner Lesepfad, kein Lock) |
| `api/routers/internal.py` | MODIFY | Neue Route `GET /api/_internal/sms/daily-usage?user_id=<...>`, Muster `stages_weather`/`loaded_trip` (Query-Pflichtparameter ohne Default) |
| `internal/handler/sms_daily_usage.go` | CREATE | Dedizierter Go-Handler, `user_id` aus `middleware.UserIDFromContext`, Timeout 1,5s, Fail-Soft bei Fehler/Timeout (liefert `204`/leeren Body statt 500) |
| `internal/router/router.go` | MODIFY | Route-Registrierung `r.Get("/api/auth/sms-daily-usage", handler.GetSmsDailyUsageHandler(*deps.Config))` neben den bestehenden `/api/auth/*`-Routen (Zeile ~94ff) |
| `frontend/src/routes/account/+page.server.ts` | MODIFY | Neuer Fetch `smsDailyUsage` im bestehenden `Promise.all(...)` (Zeilen 21-36), Fail-Soft `.catch(() => null)` |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Neuer Anzeige-Block im `account-section`-Card, Einfügestelle nach dem bestehenden "Zähler"-Block (Zeile 1065-1079), vor `data-testid="channels"` (Zeile 1082); neue Sichtbarkeits-Helferfunktion `shouldShowSmsUsageRow(limit)` |

## Implementation Details

**`src/services/sms_daily_limit.py` (MODIFY) — gemeinsamer Rollover-Helfer:**

```python
def _tagesstand(data: dict, today: str) -> dict:
    """Normalisiert einen geladenen Zaehlerstand auf den aktuellen UTC-Tag.
    Stimmt das gespeicherte Datum nicht (Tageswechsel, leere/fremde Datei),
    gilt ein frischer Nullstand -- dieselbe Regel wie bisher inline in
    `check_and_reserve`, jetzt an EINER Stelle fuer Schreib- UND Lesepfad."""
    if data.get("date") != today:
        return {"date": today, "sms": 0, "premium_sms": 0}
    return data
```

`check_and_reserve` ersetzt seine bisherigen Zeilen 174-176
(`data = _load(path); if data.get("date") != today: data = {...}`) durch
`data = _tagesstand(_load(path), today)` — funktional identisch, keine Verhaltensänderung.

**`src/services/sms_daily_limit.py` (MODIFY) — neue Lesefunktion:**

```python
def get_daily_usage(user_id: str, now: datetime) -> dict:
    """Liest den aktuellen Tagesstand fuer die Konto-Anzeige (S4b, Issue #2412).

    Rein lesend, KEIN Lock: `_write` schreibt atomar (tempfile+os.replace),
    ein gleichzeitiger Lesevorgang sieht daher immer eine vollstaendige Datei
    (alten oder neuen Stand), nie einen Teilzustand. Fail-Open bei jeder
    Stoerung (fehlende/korrupte Datei ueber `_load`/`_zaehlerwert`, kaputter
    Tarif ueber `user_tier`) liefert 0 verbrauchte Einheiten bzw. Limit 0 --
    dieselbe Philosophie wie `check_and_reserve`. Diese Funktion wirft NIE.
    """
    today = _today(now)
    data = _tagesstand(_load(_path(user_id)), today)

    try:
        sms_limit = user_tier.daily_sms_limit(user_id)
    except Exception as e:  # noqa: BLE001 -- Anzeige ist immer fail-open, anders als der Gate-Pfad (der fail-closed sperrt)
        logger.warning(
            "SMS-Tageskontingent-Anzeige: Tier-Ermittlung fuer %s fehlgeschlagen (%s) -- Limit als 0 angezeigt",
            user_id, e,
        )
        sms_limit = 0
    try:
        premium_limit = user_tier.daily_premium_sms_limit(user_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "SMS-Tageskontingent-Anzeige: Tier-Ermittlung (premium) fuer %s fehlgeschlagen (%s) -- Limit als 0 angezeigt",
            user_id, e,
        )
        premium_limit = 0

    return {
        "sms": {
            "used": _zaehlerwert(data, "sms"),
            "limit": sms_limit,
            "reserve": user_tier.SMS_ALARM_RESERVE,
        },
        "premium_sms": {
            "used": _zaehlerwert(data, "premium_sms"),
            "limit": premium_limit,
            "reserve": user_tier.PREMIUM_SMS_ALARM_RESERVE,
            "reply_overshoot": user_tier.PREMIUM_SMS_REPLY_OVERSHOOT,
        },
    }
```

**Bewusst KEIN Fail-Closed für die Anzeige** — anders als `_cap()` im Gate-Pfad (der bei
kaputter Tier-Ermittlung `cap = 0` setzt, um im Zweifel zu sperren), zeigt die Anzeige bei
demselben Fehler ebenfalls `limit = 0`. Das ist hier KEINE Sicherheitsentscheidung (die Anzeige
sperrt nichts), sondern schlicht der neutralste darstellbare Wert — ein Nutzer, dessen Tarif
nicht ermittelbar ist, sieht "0 von 0" statt eines Absturzes.

**`api/routers/internal.py` (MODIFY) — neuer Endpoint:**

```python
@router.get("/api/_internal/sms/daily-usage")
def sms_daily_usage(user_id: str = Query(...)):
    """Tageskontingent-Anzeige fuer /account (S4b, Issue #2412).

    `user_id` Pflicht-Parameter OHNE Default (Muster `loaded_trip`/`stages_weather`) --
    ein Ersatzwert wie "default" zeigte ein fremdes Konto.
    """
    return sms_daily_limit.get_daily_usage(user_id, datetime.now(timezone.utc))
```

Liegt hinter `X-GZ-Core-Auth` (bestehende Middleware `enforce_core_auth`, `api/main.py:149`) —
keine zusätzliche Absicherung nötig.

**`internal/handler/sms_daily_usage.go` (CREATE):**

```go
package handler

// SMS-/Premium-SMS-Tageskontingent-Anzeige fuer /account — Issue #2412 S4b,
// Sammel-Issue #2153, Epic #2138.
//
// Dedizierter Endpoint (NICHT in profileResponse eingebettet): /api/auth/profile
// wird auf JEDER Seite in +layout.server.ts geladen, eine Einbettung wuerde
// dort einen zusaetzlichen Python-Roundtrip einfuehren. Dieser Endpoint wird
// ausschliesslich von /account aufgerufen (Muster sms_verify.go).

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
)

func GetSmsDailyUsageHandler(cfg config.Config) http.HandlerFunc {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		target := cfg.PythonCoreURL + "/api/_internal/sms/daily-usage?user_id=" + url.QueryEscape(userId)
		resp, err := client.Get(target)
		if err != nil {
			// Fail-Soft (AC "Python-Core nicht erreichbar"): kein 500, die
			// Kontoseite bleibt vollstaendig nutzbar, nur dieser Block fehlt.
			w.WriteHeader(http.StatusNoContent)
			return
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(body)
		_ = json.Valid // Platzhalter falls spaeter Validierung noetig wird — bewusst kein Re-Marshal, Python-JSON wird 1:1 durchgereicht
	}
}
```

Anmerkung: der `json.Valid`-Kommentar-Platzhalter ist bei der Implementierung zu entfernen, falls
kein zusätzlicher Validierungsschritt eingebaut wird — reines Durchreichen der Python-Antwort ist
ausreichend, da beide Seiten unter derselben Spec-Kontrolle stehen.

**Route-Registrierung (`internal/router/router.go`, MODIFY, neben Zeile 94):**

```go
r.Get("/api/auth/sms-daily-usage", handler.GetSmsDailyUsageHandler(*deps.Config))
```

Anmeldepflichtig (nicht in der Public-Allowlist von `AuthMiddleware`) — analog `/api/auth/profile`.

**Response-Schema (Go → Frontend, 1:1 aus Python durchgereicht):**

```json
{
  "sms": { "used": 3, "limit": 10, "reserve": 2 },
  "premium_sms": { "used": 0, "limit": 15, "reserve": 3, "reply_overshoot": 3 }
}
```

Bei Fail-Soft (Timeout/Fehler): HTTP 204, leerer Body.

**Frontend `+page.server.ts` (MODIFY) — neuer Fetch im bestehenden `Promise.all`:**

```ts
fetch(`${API()}/api/auth/sms-daily-usage`, h).then(r => r.ok ? r.json() : null).catch(() => null),
```

Ergebnis als `smsDailyUsage` in den Rückgabewert von `load` aufgenommen (Muster
`premiumSmsLinkCodeExists`).

**Frontend `+page.svelte` (MODIFY) — neuer Block, Einfügestelle nach dem bestehenden
"Zähler"-Block (nach Zeile 1079), vor `data-testid="channels"`:**

```svelte
<!-- SMS-/Premium-SMS-Tageskontingent (Issue #2412 S4b) -->
{#if data.smsDailyUsage && (shouldShowSmsUsageRow(data.smsDailyUsage.sms?.limit) || shouldShowSmsUsageRow(data.smsDailyUsage.premium_sms?.limit))}
	<div data-testid="sms-daily-usage" class="mb-4">
		<p class="text-sm font-medium mb-2">SMS-Kontingent (heute)</p>
		{#if shouldShowSmsUsageRow(data.smsDailyUsage.sms?.limit)}
			<div class="flex items-center justify-between text-sm">
				<span>SMS</span>
				<span class="font-medium">
					{data.smsDailyUsage.sms.used} von {data.smsDailyUsage.sms.limit}
				</span>
			</div>
			<p class="text-xs text-muted-foreground mb-2">
				davon max. {data.smsDailyUsage.sms.limit - data.smsDailyUsage.sms.reserve} Briefings,
				{data.smsDailyUsage.sms.reserve} Alarm-Reserve
			</p>
		{/if}
		{#if shouldShowSmsUsageRow(data.smsDailyUsage.premium_sms?.limit)}
			<div class="flex items-center justify-between text-sm">
				<span>Premium-SMS</span>
				<span class="font-medium">
					{#if data.smsDailyUsage.premium_sms.used > data.smsDailyUsage.premium_sms.limit}
						{data.smsDailyUsage.premium_sms.limit} von {data.smsDailyUsage.premium_sms.limit}
						(+{data.smsDailyUsage.premium_sms.used - data.smsDailyUsage.premium_sms.limit} Antworten)
					{:else}
						{data.smsDailyUsage.premium_sms.used} von {data.smsDailyUsage.premium_sms.limit}
					{/if}
				</span>
			</div>
			<p class="text-xs text-muted-foreground">
				davon max. {data.smsDailyUsage.premium_sms.limit - data.smsDailyUsage.premium_sms.reserve} Briefings,
				{data.smsDailyUsage.premium_sms.reserve} Alarm-Reserve
			</p>
		{/if}
	</div>
{/if}
```

**Neue Sichtbarkeits-Helferfunktion** (eigene Datei oder `<script>`-Block, Muster
`shouldShowPremiumSmsLinkCard`):

```ts
export function shouldShowSmsUsageRow(limit: number | undefined): boolean {
	return typeof limit === 'number' && limit > 0;
}
```

**Begründung Sichtbarkeits-Regel (EINE Regel für beide Kanäle, kein Tier-Name-Sonderfall):** eine
Zeile wird genau dann gezeigt, wenn `limit > 0` — das deckt sowohl "Free-Tier ohne SMS-Zugriff"
(beide Kanäle `limit=0` → der gesamte Block verschwindet, da beide `{#if}`-Zweige false sind) als
auch "Standard-Tier ohne Premium-SMS-Zugriff" (`sms.limit=10`, `premium_sms.limit=0` → nur die
SMS-Zeile erscheint) mit derselben Regel ab. Eine "kein Zugriff"-Kennzeichnung würde für einen
Kanal werben, den der Nutzer gar nicht buchen kann, ohne Mehrwert (Design-Leitprinzip: klarer
Text statt zusätzlicher visueller Bausteine ohne Not) — und der bestehende Umgang mit
Premium-SMS im Account (`shouldShowPremiumSmsLinkCard`) verbirgt ebenfalls ganz, statt einen
Sperr-Zustand zu zeigen.

**Reply-Overshoot-Darstellung:** `"15 von 15 (+2 Antworten)"` statt eines geclampten `"15 von
15"` oder eines irreführenden `"17 von 15"` ohne Erklärung — der Zusatz macht sichtbar, dass die
zusätzlichen Einheiten aus Garmin-Antworten stammen (PO-Entscheidung E4, S4a), nicht aus einem
Darstellungsfehler.

## Expected Behavior

- **Input:** `user_id` aus dem Auth-Kontext (Go: `middleware.UserIDFromContext`, Python:
  Pflicht-Query-Parameter ohne Default), aktueller UTC-Zeitpunkt.
- **Output:** JSON mit `used`/`limit`/`reserve` je Kanal (`sms`, `premium_sms`), zusätzlich
  `reply_overshoot` bei `premium_sms`. Werte stammen direkt aus `user_tier`-Konstanten und dem
  aktuellen Zählerstand aus `sms_daily_count.json` — keine eigene, im Frontend gepflegte Kopie
  der Cap-Werte.
- **Side effects:** KEINE. Reiner Lesepfad — schreibt nichts, reserviert nichts, verändert keinen
  Zählerstand. Diese Anzeige hat keine eigene Gate-Wirkung; S4a bleibt alleinige
  Durchsetzungsinstanz.

## Acceptance Criteria

- **AC-1:** Given ein Standard-Nutzer hat am aktuellen UTC-Tag bereits 3 von 10 SMS verbraucht (Zählerdatei `{"sms": 3, "premium_sms": 0}` vorgeseedet) / When er `/account` aufruft / Then zeigt die Seite "3 von 10" für SMS mit dem Sub-Label "davon max. 8 Briefings, 2 Alarm-Reserve", und KEINE Premium-SMS-Zeile (Standard-Tier hat `premium_sms.limit=0`).
  - Test: Echten `GET /api/_internal/sms/daily-usage` (Python `TestClient`) sowie den Go-Handler gegen eine vorgeseedete `sms_daily_count.json` und `user.json` mit `tier=standard` ausführen; Assert auf das zurückgegebene JSON (`sms.used=3`, `sms.limit=10`, `sms.reserve=2`, kein `premium_sms.limit>0`). Zusätzlich ein Playwright-Test gegen Staging, der `/account` lädt und den sichtbaren Text "3 von 10" sowie das Sub-Label prüft, mit KEINER sichtbaren Premium-SMS-Zeile.

- **AC-2:** Given ein Premium-Nutzer hat sowohl SMS- als auch Premium-SMS-Kontingent teilverbraucht / When er `/account` aufruft / Then sieht er BEIDE Zeilen (SMS "X von 10", Premium-SMS "Y von 15") mit je eigenem Sub-Label.
  - Test: Zählerdatei mit `sms=5, premium_sms=7` vorseeden, `user.json` mit `tier=premium`; echter Endpoint-Aufruf liefert beide Kanäle mit `limit>0`; Playwright-Test prüft, dass BEIDE Zeilen im DOM sichtbar sind (`data-testid="sms-daily-usage"` enthält beide Texte).

- **AC-3:** Given ein Premium-Nutzer hat durch Garmin-Antworten sein Premium-SMS-Grundlimit überschritten (Zählerstand `premium_sms=17`, Grundlimit 15) / When er `/account` aufruft / Then zeigt die Seite "15 von 15 (+2 Antworten)" — NICHT geclampt auf "15 von 15" ohne Hinweis und NICHT unkommentiert "17 von 15".
  - Test: Zählerdatei mit `premium_sms=17` vorseeden (Reply-Overshoot-Szenario, analog S4a AC-4); echter Endpoint-Aufruf liefert `used=17, limit=15`; Frontend-Komponententest bzw. Playwright prüft exakt den Text "(+2 Antworten)" im gerenderten DOM.

- **AC-4:** Given zwei verschiedene Nutzer (`user_id` A und B) mit unterschiedlichen Zählerständen / When beide `/account` aufrufen / Then sieht jeder Nutzer AUSSCHLIESSLICH seinen eigenen Zählerstand — kein Cross-User-Leck.
  - Test: Zwei eindeutige `user_id` (Muster `_kennung`), A mit `sms=8`, B mit `sms=1`, je eigene `sms_daily_count.json`; zwei echte Requests (Go-Handler mit je eigenem Session-Kontext bzw. direkter Python-Endpoint-Aufruf mit unterschiedlichem `user_id`-Query-Parameter) liefern nachweislich unterschiedliche, korrekt zugeordnete Werte — PFLICHT-Test nach CLAUDE.md (jeder nutzerbezogene Endpoint mit zwei Nutzern).

- **AC-5:** Given der Python-Core ist nicht erreichbar (Verbindungsfehler oder Timeout > 1,5s) / When ein Nutzer `/account` aufruft / Then lädt die Seite vollständig und unverändert (Trips, Vergleiche, Kanäle, Level — alles wie gewohnt sichtbar), NUR der SMS-Kontingent-Block fehlt (kein Absturz, kein Hard-Fail, keine Fehlermeldung an prominenter Stelle).
  - Test: Go-Handler-Test mit einem `httptest.Server`, der die Verbindung sofort schließt bzw. nicht antwortet (kein Mock des HTTP-Clients selbst, ein echter, absichtlich kaputter Server) — Assert `http.StatusNoContent`. Ergänzend ein Playwright-Test gegen Staging mit simuliertem Python-Core-Ausfall (falls im Staging-Rezept vorgesehen) ODER ein Komponententest, der `smsDailyUsage: null` durchreicht und prüft, dass `data-testid="sms-daily-usage"` NICHT im DOM erscheint, während `data-testid="account-section"` und `data-testid="channels"` unverändert vorhanden sind.

- **AC-6:** Given die `sms_daily_count.json` eines Nutzers ist korrupt (kein valides JSON) / When `get_daily_usage` aufgerufen wird / Then liefert die Funktion einen neutralen Fallback (`used=0` für beide Kanäle, `limit` weiterhin aus dem Tarif) statt einer Exception.
  - Test: Direkt gegen `sms_daily_limit.get_daily_usage(user_id, now)` — Datei mit ungültigem JSON-Inhalt vorseeden (Muster `_load`-Fail-Open-Test aus S4a), Assert `result["sms"]["used"] == 0` und kein geworfener Fehler.

- **AC-7:** Given ein Free-Tier-Nutzer (kein SMS-Zugriff, beide Kanal-Limits 0) / When er `/account` aufruft / Then erscheint der gesamte SMS-Kontingent-Block NICHT (weder SMS- noch Premium-SMS-Zeile) — kein "0 von 0" und keine "kein Zugriff"-Kennzeichnung.
  - Test: `user.json` mit `tier=free`; echter Endpoint-Aufruf liefert `sms.limit=0, premium_sms.limit=0`; Playwright-Test prüft, dass `data-testid="sms-daily-usage"` NICHT im DOM vorhanden ist, während der Rest der Kontoseite normal lädt.

## Known Limitations

- **Kein Live-Update ohne Seiten-Reload.** Der Zählerstand wird beim Laden von `/account`
  einmalig abgerufen; sendet der Nutzer währenddessen in einem anderen Tab eine SMS, zeigt die
  offene Seite den alten Stand, bis sie neu geladen wird. Bewusst keine Polling-/WebSocket-Lösung
  für eine reine Informationsanzeige.
- **S4a bleibt alleinige Durchsetzungsinstanz.** Diese Anzeige ist rein informativ und hat keine
  eigene Gate-Wirkung — ein Rendering-Fehler oder eine falsche Anzeige kann niemals einen Versand
  fälschlich zulassen oder sperren, weil die Anzeige den Zähler nur liest, nie schreibt.
- **Reply-Overshoot ist nur bei `premium_sms` möglich** (Grundlimit + `PREMIUM_SMS_REPLY_OVERSHOOT`,
  S4a E4) — bei `sms` gibt es keinen Overshoot-Pfad, `used` kann dort `limit` nie überschreiten.
- **Kein separates "kein Zugriff"-Signal für gesperrte Kanäle** (AC-7) — bewusste Entscheidung
  gegen zusätzliche visuelle Bausteine ohne fachlichen Mehrwert (s. Implementation Details,
  Begründung Sichtbarkeits-Regel).
- **Fail-Soft bei Python-Core-Ausfall verbirgt den Block vollständig**, statt einen "Kontingent
  aktuell nicht abrufbar"-Platzhalter zu zeigen — Konsistenz mit dem bestehenden Muster in
  `+page.server.ts` (andere `.catch(() => null)`-Fetches verhalten sich ebenso, z.B. `scheduler`,
  `health`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Lese-/Anzeige-Pfad ohne neue Zähler-Semantik, keine neue Persistenz, kein
  neuer Architektur-Layer. Der Go-Handler folgt exakt dem in `sms_verify.go` etablierten
  Go→Python-Proxy-Muster (dedizierter Handler statt generischem `ProxyHandler`, `X-GZ-Core-Auth`
  über `coreauth.Install`, `user_id` serverseitig aus dem Auth-Kontext). Die Entscheidung, KEINEN
  generischen Proxy zu nutzen, ist keine neue Grundsatzentscheidung, sondern folgt derselben
  Mandantentrennungs-Regel wie jeder bestehende dedizierte Handler in diesem Repo (CLAUDE.md:
  echte `user_id` aus Auth-Kontext, nie `"default"`-Fallback). ADR-0049 (Premium-SMS als vierter
  Kanal) bleibt unberührt — diese Anzeige führt kein neues Tarif-Gate ein, sondern zeigt
  ausschließlich bereits bestehende `user_tier`-Werte.

## Changelog

- 2026-09-25: Initial spec created (S4b, Issue #2412, Sammel-Issue #2153, Epic #2138)
