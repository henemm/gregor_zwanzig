// TDD RED — Issue #2246 (Scheibe 1 von Epic #2199).
// Spec: docs/specs/modules/passkey_konto_verwaltung.md — AC-1 bis AC-7
//
// Auf /account fehlt heute jede Passkey-Karte; `isWebAuthnSupported()`,
// `registerPasskey()` und `deletePasskey()` aus frontend/src/lib/passkey.ts
// haben im ganzen Frontend null Aufrufer. Diese Datei misst die BEDIEN-
// OBERFLAECHE: jeder Nachweis geht ueber Knoepfe der Karte, nicht ueber
// page.evaluate()+fetch gegen die Routen (das waere die Schnittstelle, nicht
// die Karte — passkey-regression.spec.ts macht genau das und ist deshalb
// laut Spec ausdruecklich KEIN Vorbild fuer den Nachweis, nur fuer den
// Aufbau des virtuellen Authentifikators).
//
// Kein Mock: der virtuelle CDP-Authentifikator ist Chromiums eigene
// CTAP2-Implementierung, deren Signaturen der Go-Server kryptografisch
// prueft. Wo Zustand aufgebaut oder ein Nachweis serverseitig gefuehrt wird
// (Anmelde-Zeremonie fuer `last_used_at`, Anmeldeversuch mit geloeschtem
// Credential), laeuft die echte Zeremonie gegen die echten Routen.
//
// ---------------------------------------------------------------------
// UI-Vertrag, den die Implementierung erfuellen muss (RED legt ihn fest):
//   [data-testid="passkeys-card"]           Karte (aus der Spec)
//   [data-testid="passkey-row"]             je registriertem Passkey eine Zeile
//   [data-testid="passkey-last-used"]       NUR wenn last_used_at gesetzt ist
//   [data-testid="passkey-empty"]           erklaerender Text im Leerzustand
//   [data-testid="passkey-error"]           Fehlermeldung (deutsch)
//   [data-testid="passkey-unsupported"]     Hinweis ohne WebAuthn-Unterstuetzung
//   [data-testid="passkey-label-input"]     Label-Eingabe im Anlegen-Dialog
//   [data-testid="passkey-create-confirm"]  Bestaetigen im Anlegen-Dialog
//   [data-testid="passkey-create-pending"]  Wartezustand waehrend der Zeremonie
//   [data-testid="passkey-delete-confirm"]  Bestaetigen in der Loesch-Rueckfrage
//   [data-testid="passkey-delete-cancel"]   Abbrechen in der Loesch-Rueckfrage
//   Knopf "Passkey hinzufuegen" / "Loeschen" ueber ihren zugaenglichen Namen.
//
// GEMESSEN am lokalen Stack (08.09.2026): der virtuelle Authentifikator
// liefert eine Null-AAGUID, `authenticator_name` fehlt darum in der
// Profil-Antwort komplett (omitempty). Der "Geraetename" der Zeile kann in
// diesem Aufbau nur das vom Nutzer vergebene Label sein — die Karte MUSS
// also auf `label` zurueckfallen, wenn `authenticator_name` fehlt.
//
// GEMESSEN (09.09.2026): EIN Authentifikator haelt fuer EINEN Nutzer nur EIN
// auffindbares Credential. Legt man am selben Geraet einen zweiten Passkey an,
// ueberschreibt CTAP2 den ersten (gleiche rp.id + user.id) — der Server fuehrt
// danach zwei, `WebAuthn.getCredentials` nur noch einen. Das ist KEIN Defekt,
// sondern das erwartete Verhalten; zwei Passkeys eines Nutzers gibt es real nur
// auf zwei Geraeten. F001 legt deshalb ein zweites an, und zwar als
// USB-Sicherheitsschluessel: Chromium erlaubt nur EINEN internen ("platform")
// Authentifikator je Umgebung ("Chrome only supports one internal
// authenticator per environment"). Siehe `weiteresGeraetAnlegen()`.
//
// ---------------------------------------------------------------------
// 🔴 ZWEI AUFRUFE, NICHT EINER (gemessen 09.09.2026):
// Diese Datei loest 38 Anfragen auf den Passkey-Routen aus; das IP-Rate-Limit
// erlaubt 30 je Stunde (internal/router/router.go:94). EIN Lauf am Stueck
// endet deshalb zuverlaessig in HTTP 429 — sichtbar NICHT als Rate-Limit-
// Meldung, sondern als "Passkey erscheint nicht in der Liste" in den zuletzt
// laufenden Tests. Wer das fuer einen Defekt haelt, sucht an der falschen
// Stelle. Gegenmittel ist ein Neustart des Go-Servers zwischen zwei Aufrufen
// (setzt den Zaehler zurueck) — dasselbe Muster wie bei
// bug-703-login-ratelimit.spec.ts in der CI.
//
// Ausfuehrung (lokaler Stack, eigene Ports, weder Prod noch Staging):
//   cd frontend && GZ_API_BASE=http://localhost:8095 \
//     GZ_E2E_API_PROXY_TARGET=http://localhost:8095 bash e2e/start-preview.sh
//   bash frontend/e2e/run-passkey-konto.sh --reporter=list
//
// Einzelne Tests waehrend der Entwicklung (bleibt unter der Grenze):
//   cd frontend && GZ_API_BASE=http://localhost:8095 \
//     GZ_E2E_API_PROXY_TARGET=http://localhost:8095 \
//     npx playwright test e2e/passkey-konto.spec.ts --project=tests -g "F001"

import { test, expect } from '@playwright/test';
import type { CDPSession, Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

/** CDP-Antwort von WebAuthn.addVirtualAuthenticator. */
type VirtuellerAuthenticator = { authenticatorId: string };

/** Ergebnis einer echten Anmelde-Zeremonie im Browser. */
type Anmeldung = { beginStatus: number; finishStatus: number; fehler: string | null };

/** Passkey-Eintrag aus /api/auth/profile. */
type ProfilPasskey = {
	id: string;
	label?: string;
	authenticator_name?: string;
	last_used_at?: string;
};

const LABEL_BENUTZT = 'E2E-GZ-2246-Benutzt';
const LABEL_FRISCH = 'E2E-GZ-2246-Frisch';
// Zwei klar unterscheidbare Bezeichnungen fuer F001 — keine ist Teilzeichenkette
// der anderen, sonst wuerde `toContainText` beide Zeilen treffen.
const LABEL_ERSTER = 'E2E-GZ-2246-Erster';
const LABEL_ZWEITER = 'E2E-GZ-2246-Zweiter';

/** Heutiges Datum so, wie formatDate() es auf der Konto-Seite rendert (de-AT). */
function heuteFormatiert(): string {
	const d = new Date();
	const zz = (n: number) => String(n).padStart(2, '0');
	return `${zz(d.getDate())}.${zz(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/** Alle serverseitig registrierten Passkeys des angemeldeten Nutzers. */
async function serverPasskeys(page: Page): Promise<ProfilPasskey[]> {
	const res = await page.request.get('/api/auth/profile');
	expect(res.status(), 'Profil-Abruf fehlgeschlagen — Stack/Anmeldung pruefen').toBe(200);
	return ((await res.json()).passkeys ?? []) as ProfilPasskey[];
}

/** Raeumt serverseitig auf, damit jeder Test von einem bekannten Stand startet. */
async function alleServerPasskeysEntfernen(page: Page): Promise<void> {
	for (const p of await serverPasskeys(page)) {
		await page.request
			.delete(`/api/auth/passkey/credentials/${encodeURIComponent(p.id)}`)
			.catch(() => undefined);
	}
}

/**
 * Legt einen Passkey AUSSCHLIESSLICH ueber die Karte an: Knopf, Label-Eingabe,
 * Bestaetigen. Wartet nicht auf das Ergebnis — das pruefen die Tests selbst.
 */
async function passkeyUeberKarteAnlegen(page: Page, label: string): Promise<void> {
	const karte = page.getByTestId('passkeys-card');
	await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
	await page.getByTestId('passkey-label-input').fill(label);
	await page.getByTestId('passkey-create-confirm').click();
}

/**
 * Echte Anmelde-Zeremonie ohne Benutzernamen gegen die echten Routen. Wird
 * fuer den Zustandsaufbau (AC-2: `last_used_at` setzen) und fuer den
 * serverseitigen Gegenbeweis (AC-5) gebraucht — beides sind Dinge, die die
 * Karte selbst gar nicht anbietet.
 *
 * `nurCredentialId` (base64url, wie in /api/auth/profile) schraenkt die
 * Zeremonie auf GENAU dieses Credential ein — ohne diese Einschraenkung sucht
 * der Authentifikator sich bei mehreren Passkeys selbst eines aus, und der
 * Nachweis "genau DIESER ist noch anmeldefaehig" waere nicht zu fuehren
 * (F001). Nur die Auswahl im Geraet wird gesteuert; Routen, Challenge und
 * Signaturpruefung bleiben unveraendert echt.
 */
async function anmeldeZeremonieVersuchen(page: Page, nurCredentialId?: string): Promise<Anmeldung> {
	return page.evaluate(async (nurId: string | null) => {
		const b64urlToBuf = (s: string): ArrayBuffer => {
			const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
			const bin = atob(b64 + '==='.slice((b64.length + 3) % 4));
			const buf = new Uint8Array(bin.length);
			for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
			return buf.buffer;
		};
		const bufToB64url = (b: ArrayBuffer): string => {
			let s = '';
			for (const x of new Uint8Array(b)) s += String.fromCharCode(x);
			return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
		};

		const ergebnis = { beginStatus: 0, finishStatus: 0, fehler: null as string | null };
		try {
			const beginRes = await fetch('/api/auth/passkey/discoverable/begin', { method: 'POST' });
			ergebnis.beginStatus = beginRes.status;
			if (!beginRes.ok) return ergebnis;

			const pk = (await beginRes.json()).publicKey;
			const erlaubt = nurId
				? [{ type: 'public-key' as const, id: b64urlToBuf(nurId) }]
				: [];
			const assertion = (await navigator.credentials.get({
				publicKey: { ...pk, challenge: b64urlToBuf(pk.challenge), allowCredentials: erlaubt }
			})) as PublicKeyCredential | null;
			if (!assertion) {
				ergebnis.fehler = 'navigator.credentials.get lieferte null';
				return ergebnis;
			}
			const ass = assertion.response as AuthenticatorAssertionResponse;

			const finishRes = await fetch('/api/auth/passkey/discoverable/finish', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					id: assertion.id,
					rawId: bufToB64url(assertion.rawId),
					type: assertion.type,
					response: {
						authenticatorData: bufToB64url(ass.authenticatorData),
						clientDataJSON: bufToB64url(ass.clientDataJSON),
						signature: bufToB64url(ass.signature),
						userHandle: ass.userHandle ? bufToB64url(ass.userHandle) : null
					}
				})
			});
			ergebnis.finishStatus = finishRes.status;
		} catch (e) {
			ergebnis.fehler = String(e);
		}
		return ergebnis;
	}, nurCredentialId ?? null);
}

/**
 * Legt einen weiteren virtuellen Authentifikator an — ein zweites "Geraet".
 *
 * GEMESSEN (09.09.2026): ein und dasselbe Geraet haelt fuer EINEN Nutzer nur
 * EIN auffindbares Credential. Legt man am selben Authentifikator einen
 * zweiten Passkey an, ueberschreibt CTAP2 den ersten (gleiche rp.id +
 * user.id) — `WebAuthn.getCredentials` zeigt danach nur noch den zweiten,
 * waehrend der Server beide fuehrt. Zwei Passkeys eines Nutzers gibt es real
 * also nur auf zwei Geraeten; der Nachweis in F001 braucht darum zwei.
 */
async function weiteresGeraetAnlegen(cdp: CDPSession): Promise<string> {
	// GEMESSEN: Chromium laesst nur EINEN internen ("platform") Authentifikator
	// je Umgebung zu — das zweite Geraet ist deshalb ein Sicherheitsschluessel
	// am USB-Anschluss. Der Server verlangt nur `residentKey: required`, keine
	// Bauform (internal/handler/passkey.go:481), beide Wege sind also echt.
	const antwort = (await cdp.send('WebAuthn.addVirtualAuthenticator', {
		options: {
			protocol: 'ctap2',
			transport: 'usb',
			hasResidentKey: true,
			hasUserVerification: true,
			isUserVerified: true,
			automaticPresenceSimulation: true
		}
	})) as unknown as VirtuellerAuthenticator;
	return antwort.authenticatorId;
}

/** Credential-IDs (base64url wie in /api/auth/profile) eines Geraets. */
async function credentialIdsImGeraet(cdp: CDPSession, geraetId: string): Promise<string[]> {
	const antwort = (await cdp.send('WebAuthn.getCredentials', {
		authenticatorId: geraetId
	})) as unknown as { credentials: { credentialId: string }[] };
	return antwort.credentials.map((c) =>
		c.credentialId.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
	);
}

/**
 * Bedienbarkeit statt blosser Sichtbarkeit: toBeVisible() sagt nichts darueber,
 * ob ein anderes Element den Knopf ueberdeckt. Hier wird der Mittelpunkt des
 * Elements per elementFromPoint zurueckgetroffen.
 */
async function istWirklichAnklickbar(page: Page, testid: string): Promise<boolean> {
	await page.getByTestId(testid).scrollIntoViewIfNeeded().catch(() => undefined);
	return page.evaluate((id) => {
		const el = document.querySelector(`[data-testid="${id}"]`);
		if (!el) return false;
		const r = el.getBoundingClientRect();
		if (r.width < 1 || r.height < 1) return false;
		const treffer = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
		return !!treffer && (treffer === el || el.contains(treffer) || treffer.contains(el));
	}, testid);
}

test.describe('Passkey-Karte auf der Konto-Seite (#2246)', () => {
	let cdp: CDPSession;
	let authenticatorId = '';

	test.beforeEach(async ({ page, context, baseURL }) => {
		// Issue #1265: niemals gegen Produktion.
		assertNotProdBaseURL(baseURL ?? '');

		cdp = await context.newCDPSession(page);
		await cdp.send('WebAuthn.enable');
		const antwort = (await cdp.send('WebAuthn.addVirtualAuthenticator', {
			options: {
				protocol: 'ctap2',
				transport: 'internal',
				hasResidentKey: true,
				hasUserVerification: true,
				isUserVerified: true,
				automaticPresenceSimulation: true
			}
		})) as unknown as VirtuellerAuthenticator;
		authenticatorId = antwort.authenticatorId;

		// Bekannter Ausgangsstand: der E2E-Nutzer hat keinen Passkey. Ohne das
		// haengen Reste frueherer Laeufe am Konto und verfaelschen jede
		// Zaehlung — besonders den Leerzustand (AC-3).
		await page.goto('/account');
		await alleServerPasskeysEntfernen(page);
	});

	test.afterEach(async ({ page }) => {
		// Die Tests legen ECHTE Passkeys am E2E-Nutzer an — ohne Aufraeumen
		// haengen sie dauerhaft dort und verbrauchen zusaetzlich das
		// IP-Rate-Limit (30 Passkey-Anfragen/Stunde, internal/router/router.go:94).
		await alleServerPasskeysEntfernen(page).catch(() => undefined);
		if (authenticatorId) {
			await cdp
				.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId })
				.catch(() => undefined);
			authenticatorId = '';
		}
	});

	// -------------------------------------------------------------------
	// AC-1: die Karte existiert und steht zwischen "Kanaele" und
	// "Passwort aendern" — gemessen an der DOM-Reihenfolge, nicht an blosser
	// Existenz.
	// -------------------------------------------------------------------
	test('AC-1: Passkey-Karte steht zwischen "Kanäle" und "Passwort ändern"', async ({ page }) => {
		await page.goto('/account');

		const karte = page.getByTestId('passkeys-card');
		await expect(karte, 'auf /account gibt es keine Karte mit data-testid="passkeys-card"').toHaveCount(1);
		await expect(karte).toBeVisible();

		const reihenfolge = await page.evaluate(() => {
			const karten = Array.from(document.querySelectorAll('[data-slot="card"]'));
			const titel = (k: Element) =>
				k.querySelector('[data-slot="card-title"]')?.textContent?.trim() ?? '';
			return {
				kanaele: karten.findIndex((k) => titel(k) === 'Kanäle'),
				passkeys: karten.findIndex((k) => k.getAttribute('data-testid') === 'passkeys-card'),
				passwort: karten.findIndex((k) => titel(k) === 'Passwort ändern'),
				anzahl: karten.length
			};
		});

		expect(reihenfolge.kanaele, 'Karte "Kanäle" nicht gefunden').toBeGreaterThanOrEqual(0);
		expect(reihenfolge.passwort, 'Karte "Passwort ändern" nicht gefunden').toBeGreaterThanOrEqual(0);
		expect(reihenfolge.passkeys, 'Passkey-Karte nicht unter den Karten').toBeGreaterThanOrEqual(0);
		expect(
			reihenfolge.kanaele,
			`Passkey-Karte steht nicht NACH "Kanäle" (Positionen: ${JSON.stringify(reihenfolge)})`
		).toBeLessThan(reihenfolge.passkeys);
		expect(
			reihenfolge.passkeys,
			`Passkey-Karte steht nicht VOR "Passwort ändern" (Positionen: ${JSON.stringify(reihenfolge)})`
		).toBeLessThan(reihenfolge.passwort);
	});

	// -------------------------------------------------------------------
	// AC-2: benutzter Passkey zeigt ein Datum der letzten Verwendung, nie
	// benutzter zeigt KEIN erfundenes Datum. Beide Zustaende werden ECHT
	// aufgebaut: Passkey A wird angelegt und dann mit einer echten
	// Anmelde-Zeremonie benutzt (Server setzt last_used_at), Passkey B wird
	// danach angelegt und nie benutzt.
	// -------------------------------------------------------------------
	test('AC-2: benutzter Passkey zeigt "zuletzt verwendet", unbenutzter kein erfundenes Datum', async ({
		page
	}) => {
		await page.goto('/account');

		await passkeyUeberKarteAnlegen(page, LABEL_BENUTZT);
		await expect(page.getByTestId('passkey-row')).toHaveCount(1);

		// Echte Anmeldung — erst dadurch setzt der Server last_used_at.
		const anmeldung = await anmeldeZeremonieVersuchen(page);
		expect(anmeldung.fehler, 'die Anmelde-Zeremonie brach im Browser ab').toBeNull();
		expect(anmeldung.finishStatus, 'Anmeldung mit dem eben angelegten Passkey scheiterte').toBe(200);

		await page.goto('/account');
		await passkeyUeberKarteAnlegen(page, LABEL_FRISCH);
		await expect(page.getByTestId('passkey-row')).toHaveCount(2);

		// Messgrundlage: der Server fuehrt genau EINEN Passkey mit last_used_at.
		const vomServer = await serverPasskeys(page);
		expect(vomServer.filter((p) => p.last_used_at).length).toBe(1);
		expect(vomServer.filter((p) => !p.last_used_at).length).toBe(1);

		await page.goto('/account');
		const heute = heuteFormatiert();
		const karte = page.getByTestId('passkeys-card');
		const benutzt = karte.getByTestId('passkey-row').filter({ hasText: LABEL_BENUTZT });
		const frisch = karte.getByTestId('passkey-row').filter({ hasText: LABEL_FRISCH });

		await expect(benutzt, `keine Zeile mit dem Gerätenamen "${LABEL_BENUTZT}"`).toHaveCount(1);
		await expect(frisch, `keine Zeile mit dem Gerätenamen "${LABEL_FRISCH}"`).toHaveCount(1);

		// Anlagedatum steht in beiden Zeilen.
		await expect(benutzt, 'Anlagedatum fehlt in der Zeile des benutzten Passkeys').toContainText(heute);
		await expect(frisch, 'Anlagedatum fehlt in der Zeile des unbenutzten Passkeys').toContainText(heute);

		// Benutzter Passkey: eigenes Feld fuer die letzte Verwendung, mit Datum.
		const letzteVerwendung = benutzt.getByTestId('passkey-last-used');
		await expect(
			letzteVerwendung,
			'der benutzte Passkey zeigt kein Feld "zuletzt verwendet"'
		).toHaveCount(1);
		await expect(letzteVerwendung).toContainText(heute);

		// Unbenutzter Passkey: entweder gar kein Feld — oder eines OHNE Datum.
		// Genau hier faellt "Anlagedatum als letzte Verwendung durchgereicht" auf.
		const frischLetzte = frisch.getByTestId('passkey-last-used');
		const anzahlFrisch = await frischLetzte.count();
		if (anzahlFrisch > 0) {
			const text = (await frischLetzte.innerText()).trim();
			expect(
				text,
				`der nie benutzte Passkey zeigt ein Datum als letzte Verwendung ("${text}") — erfundener Wert`
			).not.toMatch(/\d{1,2}\.\d{1,2}\.\d{4}/);
		}
	});

	// -------------------------------------------------------------------
	// AC-3: Leerzustand — erklaerender Text statt Liste, Anlegen bleibt
	// sichtbar UND bedienbar (nicht nur im DOM).
	// -------------------------------------------------------------------
	test('AC-3: Leerzustand zeigt erklärenden Text, Anlegen bleibt bedienbar', async ({ page }) => {
		await page.goto('/account');

		const karte = page.getByTestId('passkeys-card');
		await expect(karte).toBeVisible();
		await expect(karte.getByTestId('passkey-row'), 'ohne Passkeys darf keine Zeile stehen').toHaveCount(0);

		const hinweis = karte.getByTestId('passkey-empty');
		await expect(hinweis, 'kein erklärender Hinweis im Leerzustand').toHaveCount(1);
		const hinweisText = (await hinweis.innerText()).trim();
		expect(
			hinweisText.length,
			`der Hinweis im Leerzustand erklärt nichts ("${hinweisText}")`
		).toBeGreaterThanOrEqual(20);
		expect(hinweisText).toMatch(/Passkey/i);

		const anlegen = karte.getByRole('button', { name: 'Passkey hinzufügen' });
		await expect(anlegen, 'der Anlegen-Knopf fehlt im Leerzustand').toHaveCount(1);
		await expect(anlegen).toBeEnabled();
		expect(
			await istWirklichAnklickbar(page, 'passkeys-card'),
			'die Passkey-Karte ist überdeckt oder hat keine Fläche'
		).toBe(true);

		// Bedienbar heisst: der Klick oeffnet den Anlegen-Weg wirklich.
		await anlegen.click();
		await expect(
			page.getByTestId('passkey-create-confirm'),
			'der Anlegen-Knopf reagiert nicht — kein bedienbarer Weg zum Anlegen'
		).toBeVisible();
	});

	// -------------------------------------------------------------------
	// AC-4: nach erfolgreichem Anlegen erscheint der Eintrag OHNE
	// Seiten-Neuladen. Das Nicht-Neuladen wird ueber eine vorher gesetzte
	// Marke auf window belegt — ein Reload wuerde sie loeschen.
	// -------------------------------------------------------------------
	test('AC-4: neuer Passkey erscheint ohne Seiten-Neuladen', async ({ page }) => {
		await page.goto('/account');
		await expect(page.getByTestId('passkeys-card')).toBeVisible();

		await page.evaluate(() => {
			(window as unknown as Record<string, string>).__gz2246Marke = 'vor-dem-anlegen';
		});

		await passkeyUeberKarteAnlegen(page, LABEL_FRISCH);

		const zeile = page.getByTestId('passkeys-card').getByTestId('passkey-row');
		await expect(zeile, 'der neue Passkey erscheint nicht in der Liste').toHaveCount(1);
		await expect(zeile).toContainText(LABEL_FRISCH);

		// Seit AC-9 bleibt der Dialog waehrend der Zeremonie offen — nach einer
		// ERFOLGREICHEN Zeremonie muss er zugehen. AC-9 selbst belegt nur den
		// Fehlerweg; ohne diese Zeile bliebe das Schliessen bei Erfolg ungeprueft.
		await expect(
			page.getByTestId('passkey-create-confirm'),
			'der Anlegen-Dialog bleibt nach der erfolgreichen Zeremonie offen stehen'
		).toBeHidden();

		const marke = await page.evaluate(
			() => (window as unknown as Record<string, string>).__gz2246Marke
		);
		expect(
			marke,
			'die window-Marke ist verschwunden — die Seite wurde neu geladen statt die Liste zu aktualisieren'
		).toBe('vor-dem-anlegen');

		// Gegenprobe: serverseitig existiert der Passkey wirklich.
		expect((await serverPasskeys(page)).length).toBe(1);
	});

	// -------------------------------------------------------------------
	// AC-5: Loeschen entfernt den Eintrag aus der Liste UND macht das
	// Credential serverseitig wirkungslos. Der zweite Teil ist der
	// eigentliche Nachweis — ohne ihn misst der Test nur die Anzeige.
	// -------------------------------------------------------------------
	test('AC-5: Löschen entfernt den Eintrag und macht das Credential serverseitig wirkungslos', async ({
		page
	}) => {
		await page.goto('/account');
		await passkeyUeberKarteAnlegen(page, LABEL_FRISCH);

		const zeile = page.getByTestId('passkeys-card').getByTestId('passkey-row');
		await expect(zeile).toHaveCount(1);

		const vorher = await serverPasskeys(page);
		expect(vorher.length).toBe(1);
		const geloeschteId = vorher[0].id;

		// Vorprobe: mit diesem Credential ist eine Anmeldung JETZT moeglich —
		// sonst bewiese das spaetere Scheitern nichts.
		const vorprobe = await anmeldeZeremonieVersuchen(page);
		expect(vorprobe.fehler).toBeNull();
		expect(
			vorprobe.finishStatus,
			'vor dem Löschen war schon keine Anmeldung möglich — der Nachweis danach wäre wertlos'
		).toBe(200);

		await page.goto('/account');
		// Seit AC-8 fragt das Loeschen zuerst nach; der Nachweis unten bleibt
		// unveraendert, nur der Weg dorthin hat einen Schritt mehr.
		await zeile.getByRole('button', { name: 'Löschen' }).click();
		await page.getByTestId('passkey-delete-confirm').click();

		await expect(zeile, 'der Eintrag verschwindet nach dem Löschen nicht aus der Liste').toHaveCount(0);
		const nachher = await serverPasskeys(page);
		expect(nachher.map((p) => p.id)).not.toContain(geloeschteId);

		// Der eigentliche Nachweis: dasselbe Credential liegt weiter im
		// Authentifikator, der Server nimmt es aber nicht mehr an.
		const danach = await anmeldeZeremonieVersuchen(page);
		expect(
			danach.finishStatus,
			'der Server akzeptiert das gelöschte Credential weiterhin — es wurde nur aus der Anzeige entfernt'
		).toBe(401);
	});

	// -------------------------------------------------------------------
	// AC-6: ohne WebAuthn-Unterstuetzung. Die Bedingung wird ECHT im Browser
	// erzeugt (window.PublicKeyCredential vor dem Seitenaufbau entfernt),
	// nicht durch Abfangen von isWebAuthnSupported().
	// -------------------------------------------------------------------
	test('AC-6: ohne WebAuthn bleibt die Karte sichtbar, der Anlegen-Knopf entfällt', async ({
		page
	}) => {
		await page.addInitScript(() => {
			// @ts-expect-error absichtlich: Browser ohne WebAuthn nachstellen
			delete window.PublicKeyCredential;
			Object.defineProperty(window, 'PublicKeyCredential', {
				value: undefined,
				configurable: true
			});
		});
		await page.goto('/account');

		expect(
			await page.evaluate(() => typeof (window as Record<string, unknown>).PublicKeyCredential),
			'window.PublicKeyCredential ist noch da — die Bedingung wurde gar nicht hergestellt'
		).toBe('undefined');

		const karte = page.getByTestId('passkeys-card');
		await expect(karte, 'die Karte verschwindet ohne WebAuthn — sie soll sichtbar bleiben').toBeVisible();

		await expect(
			karte.getByRole('button', { name: 'Passkey hinzufügen' }),
			'der Anlegen-Knopf steht trotz fehlender WebAuthn-Unterstützung da'
		).toHaveCount(0);

		const hinweis = karte.getByTestId('passkey-unsupported');
		await expect(hinweis, 'kein Hinweistext an Stelle des Anlegen-Knopfs').toHaveCount(1);
		const text = (await hinweis.innerText()).trim();
		expect(text.length, `der Hinweis erklärt nichts ("${text}")`).toBeGreaterThanOrEqual(20);
		expect(text, 'der Hinweis ist nicht auf Deutsch verfasst').toMatch(
			/unterstützt|unterstützen|Browser|Gerät/i
		);
	});

	// -------------------------------------------------------------------
	// AC-7: Zeremonie laeuft in eine Zeitueberschreitung. Echt erzeugt: der
	// virtuelle Authentifikator bestaetigt die Nutzerpraesenz nicht mehr, und
	// die vom Server gelieferte Frist wird von 300 s auf 4 s verkuerzt (nur
	// dieser eine Zahlenwert — Challenge, Zeremonie und Fehlerweg bleiben
	// echt; gemessen: Chromium haelt kurze Fristen auf die Millisekunde ein
	// und antwortet mit NotAllowedError).
	// -------------------------------------------------------------------
	test('AC-7: gescheiterte Zeremonie zeigt eine deutsche Fehlermeldung, die Liste bleibt unverändert', async ({
		page
	}) => {
		test.setTimeout(60_000);
		await page.goto('/account');

		// Ausgangsstand mit EINEM Eintrag — "Liste bleibt unveraendert" ist
		// sonst nur die Aussage 0 == 0 und wuerde einen halben Eintrag nicht
		// von einem leeren Zustand unterscheiden.
		await passkeyUeberKarteAnlegen(page, LABEL_BENUTZT);
		const zeilen = page.getByTestId('passkeys-card').getByTestId('passkey-row');
		await expect(zeilen).toHaveCount(1);

		await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
			authenticatorId,
			enabled: false
		});
		await page.route('**/api/auth/passkey/register/begin', async (route) => {
			const antwort = await route.fetch();
			const koerper = await antwort.json();
			koerper.publicKey.timeout = 4000;
			await route.fulfill({ response: antwort, json: koerper });
		});

		await passkeyUeberKarteAnlegen(page, LABEL_FRISCH);

		const fehler = page.getByTestId('passkey-error');
		await expect(fehler, 'nach der gescheiterten Zeremonie erscheint keine Fehlermeldung').toBeVisible({
			timeout: 30_000
		});
		const text = (await fehler.innerText()).trim();
		expect(text.length, `die Fehlermeldung sagt nichts ("${text}")`).toBeGreaterThanOrEqual(15);
		expect(
			text,
			`die Fehlermeldung ist ein technischer Rohtext ("${text}") statt verständlichem Deutsch`
		).not.toMatch(/register_(begin|finish)_failed|NotAllowedError|TypeError|undefined/);
		expect(text, 'die Fehlermeldung ist nicht auf Deutsch').toMatch(
			/abgebrochen|fehlgeschlagen|nicht|Zeit/i
		);

		// Liste unveraendert — kein halber Eintrag, weder in der Anzeige …
		await expect(
			zeilen,
			'nach der gescheiterten Zeremonie steht ein zusätzlicher Eintrag in der Liste'
		).toHaveCount(1);
		await expect(zeilen).toContainText(LABEL_BENUTZT);
		// … noch auf dem Server.
		const vomServer = await serverPasskeys(page);
		expect(
			vomServer.length,
			'der Server hat trotz gescheiterter Zeremonie einen Passkey angelegt'
		).toBe(1);
		expect(vomServer[0].label).toBe(LABEL_BENUTZT);
	});

	// -------------------------------------------------------------------
	// AC-8: das Loeschen fragt zuerst nach. Der Nachweis ist der ABBRUCH —
	// und zwar nicht "die Zeile steht noch da" (das uebersieht ein stilles
	// Loeschen im Hintergrund, weil die Anzeige erst beim naechsten Abruf
	// nachzieht), sondern eine echte Anmelde-Zeremonie mit genau diesem
	// Credential. Sie ist die Umkehrung des AC-5-Nachweises: dort muss der
	// Server das Credential ablehnen, hier muss er es weiter annehmen.
	// -------------------------------------------------------------------
	test('AC-8: Abbrechen der Rückfrage lässt den Passkey anmeldefähig, erst Bestätigen entfernt ihn', async ({
		page
	}) => {
		await page.goto('/account');
		await passkeyUeberKarteAnlegen(page, LABEL_FRISCH);

		const zeile = page.getByTestId('passkeys-card').getByTestId('passkey-row');
		await expect(zeile).toHaveCount(1);

		const vorher = await serverPasskeys(page);
		expect(vorher.length).toBe(1);
		const id = vorher[0].id;

		// Erster Anlauf: der Knopf darf nicht sofort loeschen, sondern muss fragen.
		await zeile.getByRole('button', { name: 'Löschen' }).click();
		const bestaetigen = page.getByTestId('passkey-delete-confirm');
		await expect(
			bestaetigen,
			'der Löschen-Knopf löscht ohne Rückfrage — es erscheint kein Bestätigungsdialog'
		).toBeVisible();

		await page.getByTestId('passkey-delete-cancel').click();
		await expect(bestaetigen, 'die Rückfrage bleibt nach dem Abbrechen offen stehen').toBeHidden();

		// Anzeige unveraendert …
		await expect(zeile, 'nach dem Abbruch fehlt der Eintrag in der Liste').toHaveCount(1);
		// … Server fuehrt das Credential weiter …
		expect(
			(await serverPasskeys(page)).map((p) => p.id),
			'nach dem Abbruch ist der Passkey serverseitig verschwunden'
		).toContain(id);
		// … und der eigentliche Nachweis: es taugt weiterhin zur Anmeldung.
		const anmeldung = await anmeldeZeremonieVersuchen(page);
		expect(anmeldung.fehler, 'die Anmelde-Zeremonie brach im Browser ab').toBeNull();
		expect(
			anmeldung.finishStatus,
			'nach dem Abbruch der Rückfrage lehnt der Server das Credential ab — es wurde im Hintergrund doch gelöscht'
		).toBe(200);

		// Zweiter Anlauf: erst das Bestaetigen entfernt ihn wirklich.
		await page.goto('/account');
		await zeile.getByRole('button', { name: 'Löschen' }).click();
		await page.getByTestId('passkey-delete-confirm').click();
		await expect(zeile, 'nach dem Bestätigen verschwindet der Eintrag nicht').toHaveCount(0);
		expect(
			(await serverPasskeys(page)).map((p) => p.id),
			'nach dem Bestätigen führt der Server den Passkey weiter'
		).not.toContain(id);
	});

	// -------------------------------------------------------------------
	// AC-9: waehrend die Zeremonie am Geraet aussteht, bleibt der Dialog
	// offen und "Anlegen" ist gesperrt. Damit dieser Zustand ueberhaupt
	// messbar lange steht, bestaetigt der virtuelle Authentifikator die
	// Nutzerpraesenz nicht mehr; die vom Server gelieferte Frist wird auf
	// FRIST_MS verkuerzt (derselbe Griff wie in AC-7 — nur dieser eine
	// Zahlenwert, Zeremonie und Fehlerweg bleiben echt), damit die Zeremonie
	// zu einem bekannten Zeitpunkt endet.
	//
	// GEMESSEN (08.09.2026): WebAuthn.setAutomaticPresenceSimulation(true)
	// weckt eine bereits laufende create()-Anfrage in Chromium NICHT auf —
	// sie laeuft trotzdem in die Frist. Das Ende der Zeremonie muss deshalb
	// ueber die Frist herbeigefuehrt werden, nicht ueber die Praesenz.
	//
	// Der Messzeitpunkt liegt nachweislich MITTENDRIN: nach der Antwort auf
	// register/begin, vor Ablauf der Frist (Zeitstempel wird geprueft) und
	// bevor irgendeine Meldung erschienen ist.
	// -------------------------------------------------------------------
	test('AC-9: der Anlegen-Dialog bleibt während der Zeremonie offen und sperrt "Anlegen"', async ({
		page
	}) => {
		test.setTimeout(60_000);
		const FRIST_MS = 8000;
		await page.goto('/account');

		await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
			authenticatorId,
			enabled: false
		});
		await page.route('**/api/auth/passkey/register/begin', async (route) => {
			const antwort = await route.fetch();
			const koerper = await antwort.json();
			koerper.publicKey.timeout = FRIST_MS;
			await route.fulfill({ response: antwort, json: koerper });
		});

		const begonnen = page.waitForResponse('**/api/auth/passkey/register/begin');
		const karte = page.getByTestId('passkeys-card');
		await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
		await page.getByTestId('passkey-label-input').fill(LABEL_FRISCH);
		const bestaetigen = page.getByTestId('passkey-create-confirm');
		await bestaetigen.click();

		// Ab hier laeuft die Zeremonie wirklich — vorher waere jede Messung wertlos.
		await begonnen;
		const zeremonieStart = Date.now();

		await expect(
			bestaetigen,
			'der Dialog schließt sich, obwohl die Bestätigung am Gerät noch aussteht'
		).toBeVisible();
		await expect(
			bestaetigen,
			'"Anlegen" ist während der laufenden Zeremonie nicht gesperrt'
		).toBeDisabled();

		const warten = page.getByTestId('passkey-create-pending');
		await expect(
			warten,
			'kein erkennbarer Hinweis, dass die Bestätigung am Gerät aussteht'
		).toBeVisible();
		const wartetext = (await warten.innerText()).trim();
		expect(wartetext.length, `der Wartehinweis sagt nichts ("${wartetext}")`).toBeGreaterThanOrEqual(
			15
		);
		expect(wartetext, 'der Wartehinweis ist nicht auf Deutsch').toMatch(/Gerät|bestätig/i);

		// Zu allen Pruefungen oben war noch keine Meldung da …
		await expect(
			page.getByTestId('passkey-error'),
			'zum Messzeitpunkt lag bereits ein Ergebnis vor — geprueft wurde also nicht der Wartezustand'
		).toHaveCount(0);
		// … und die Frist der Zeremonie war noch nicht abgelaufen.
		expect(
			Date.now() - zeremonieStart,
			'die Messung fiel hinter das Ende der Zeremonie — der Wartezustand wurde nicht belegt'
		).toBeLessThan(FRIST_MS);

		// Ende der Zeremonie (hier: Fristablauf) — erst jetzt geht der Dialog zu.
		await expect(
			page.getByTestId('passkey-error'),
			'die beendete Zeremonie bleibt ohne Rückmeldung'
		).toBeVisible({ timeout: 30_000 });
		await expect(
			bestaetigen,
			'der Dialog bleibt nach der beendeten Zeremonie offen stehen'
		).toBeHidden();
	});

	// -------------------------------------------------------------------
	// F001 (Adversary #2246): AC-5 und AC-8 arbeiten mit genau EINEM Passkey.
	// Dort sind `pk` und `passkeys[0]` dasselbe — eine Regression an der
	// Zielauswahl der Rueckfrage (falscher Index, stale Closure) faellt darum
	// nicht auf. Hier stehen ZWEI Passkeys in der Liste, geloescht wird der
	// ZWEITE. Geprueft wird an drei Stellen: die Rueckfrage nennt den richtigen
	// Namen (sonst bestaetigt der Nutzer blind), der Server fuehrt danach genau
	// den ersten weiter — und der erste ist weiterhin ANMELDEFAEHIG, belegt
	// ueber eine echte Zeremonie, die gezielt genau dieses Credential verlangt.
	// -------------------------------------------------------------------
	test('F001: die Rückfrage trifft den angeklickten Passkey, nicht den ersten der Liste', async ({
		page
	}) => {
		await page.goto('/account');

		// Geraet A: der erste Passkey.
		await passkeyUeberKarteAnlegen(page, LABEL_ERSTER);
		const zeilen = page.getByTestId('passkeys-card').getByTestId('passkey-row');
		await expect(zeilen).toHaveCount(1);

		// Geraet B: der zweite. Waehrend der Zeremonie bestaetigt nur B die
		// Nutzerpraesenz — sonst entschiede der Zufall, welches Geraet antwortet.
		await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
			authenticatorId,
			enabled: false
		});
		const geraetB = await weiteresGeraetAnlegen(cdp);
		await passkeyUeberKarteAnlegen(page, LABEL_ZWEITER);
		await expect(zeilen, 'der zweite Passkey erscheint nicht in der Liste').toHaveCount(2);

		// Messgrundlage: welche ID gehoert zu welcher Bezeichnung — und liegt
		// wirklich je eine auf einem eigenen Geraet?
		const vorher = await serverPasskeys(page);
		expect(vorher.length, 'der Ausgangsstand hat nicht genau zwei Passkeys').toBe(2);
		const ersterId = vorher.find((p) => p.label === LABEL_ERSTER)?.id ?? '';
		const zweiterId = vorher.find((p) => p.label === LABEL_ZWEITER)?.id ?? '';
		expect(ersterId, `kein Passkey mit Label "${LABEL_ERSTER}" am Server`).toBeTruthy();
		expect(zweiterId, `kein Passkey mit Label "${LABEL_ZWEITER}" am Server`).toBeTruthy();
		expect(ersterId).not.toBe(zweiterId);
		expect(
			await credentialIdsImGeraet(cdp, authenticatorId),
			'der erste Passkey liegt nicht auf dem ersten Gerät — der Aufbau misst nicht zwei Geräte'
		).toEqual([ersterId]);
		expect(
			await credentialIdsImGeraet(cdp, geraetB),
			'der zweite Passkey liegt nicht auf dem zweiten Gerät'
		).toEqual([zweiterId]);

		// Loeschen am ZWEITEN Eintrag anstossen.
		const zweiteZeile = zeilen.filter({ hasText: LABEL_ZWEITER });
		await expect(zweiteZeile).toHaveCount(1);
		await zweiteZeile.getByRole('button', { name: 'Löschen' }).click();

		// Die Rueckfrage muss den angeklickten Passkey benennen — nennt sie den
		// falschen, bestaetigt der Nutzer eine Loeschung, die er nicht wollte.
		const rueckfrage = page
			.locator('[data-slot="dialog-content"]')
			.filter({ has: page.getByTestId('passkey-delete-confirm') });
		await expect(rueckfrage, 'es erscheint keine Rückfrage').toBeVisible();
		await expect(
			rueckfrage,
			`die Rückfrage nennt nicht den angeklickten Passkey "${LABEL_ZWEITER}"`
		).toContainText(LABEL_ZWEITER);
		await expect(
			rueckfrage,
			`die Rückfrage nennt "${LABEL_ERSTER}" — also den falschen Passkey`
		).not.toContainText(LABEL_ERSTER);

		await page.getByTestId('passkey-delete-confirm').click();

		// Anzeige: genau der erste bleibt stehen.
		await expect(
			zeilen,
			'nach dem Löschen steht nicht mehr genau eine Zeile in der Liste'
		).toHaveCount(1);
		await expect(
			zeilen,
			'in der Liste steht nach dem Löschen nicht der erste, sondern ein anderer Passkey'
		).toContainText(LABEL_ERSTER);
		await expect(zeilen).not.toContainText(LABEL_ZWEITER);

		// Server: genau die angeklickte ID ist weg, die andere ist da.
		const nachher = (await serverPasskeys(page)).map((p) => p.id);
		expect(
			nachher,
			'der angeklickte (zweite) Passkey liegt weiterhin am Server — gelöscht wurde ein anderer'
		).not.toContain(zweiterId);
		expect(
			nachher,
			'der NICHT angeklickte (erste) Passkey wurde mitgelöscht — falsches Löschziel'
		).toContain(ersterId);

		// Der eigentliche Nachweis: das erste Gerät meldet sich weiterhin an.
		// Jetzt bestaetigt wieder nur A die Praesenz, und die Zeremonie verlangt
		// gezielt dessen Credential — sonst antwortete moeglicherweise B.
		await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
			authenticatorId,
			enabled: true
		});
		await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
			authenticatorId: geraetB,
			enabled: false
		});
		const anmeldung = await anmeldeZeremonieVersuchen(page, ersterId);
		expect(anmeldung.fehler, 'die Anmelde-Zeremonie brach im Browser ab').toBeNull();
		expect(
			anmeldung.finishStatus,
			'der nicht angeklickte Passkey ist nach dem Löschen nicht mehr anmeldefähig — es wurde der falsche entfernt'
		).toBe(200);

		await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId: geraetB });
	});

	// -------------------------------------------------------------------
	// F002 (Adversary #2246): AC-9 belegt nur den natuerlichen Ablauf. Es gibt
	// aber DREI weitere Wege, den Dialog zu schliessen — Escape, Klick neben
	// den Dialog und das X in der Ecke. Alle drei gehen an `createPasskey()`
	// vorbei; jeder braucht seinen eigenen Schutz an `Dialog.Content`
	// (`escapeKeydownBehavior`, `interactOutsideBehavior`, `showCloseButton`).
	//
	// GEMESSEN (09.09.2026, vor dem Fix): alle drei schlossen den Dialog
	// mitten in der Zeremonie — X nach 77 ms, Aussenklick nach 766 ms, Escape
	// nach 1473 ms, jeweils bei einer Frist von 10 s, mit noch gesetztem
	// `passkeyBusy` und ohne jede Rueckmeldung. Der Waechter in `onOpenChange`
	// konnte das nicht verhindern: die Dialog-Primitive schliesst ihren
	// eigenen Zustand selbst und meldet es nur noch.
	//
	// Die drei Wege werden NACHEINANDER geprueft — faellt der erste, sagt der
	// Test nichts ueber die anderen. Wer hier etwas aendert, prueft jeden
	// Schutz einzeln gegen seinen Abschnitt.
	//
	// Messtechnik wie AC-9: die Zeremonie steht nachweislich aus (Antwort auf
	// register/begin ist da, Frist noch nicht abgelaufen, noch keine Meldung
	// sichtbar).
	// -------------------------------------------------------------------
	test('F002: Escape, Klick neben den Dialog und das X schließen ihn während der Zeremonie nicht', async ({
		page
	}) => {
		test.setTimeout(60_000);
		const FRIST_MS = 10_000;
		// Beobachtungsfenster nach jedem Schliessversuch. Ein "sofort noch
		// sichtbar" waere wertlos — der Dialog schliesst mit einer Animation.
		// Geprueft wird deshalb, dass er in diesem Fenster NICHT verschwindet;
		// das Fenster bleibt deutlich innerhalb der Frist der Zeremonie.
		const BEOBACHTUNG_MS = 700;

		/** true, wenn der Dialog im Beobachtungsfenster verschwindet. */
		const dialogVerschwindet = () =>
			page
				.getByTestId('passkey-create-confirm')
				.waitFor({ state: 'detached', timeout: BEOBACHTUNG_MS })
				.then(() => true)
				.catch(() => false);

		await page.goto('/account');

		await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
			authenticatorId,
			enabled: false
		});
		await page.route('**/api/auth/passkey/register/begin', async (route) => {
			const antwort = await route.fetch();
			const koerper = await antwort.json();
			koerper.publicKey.timeout = FRIST_MS;
			await route.fulfill({ response: antwort, json: koerper });
		});

		const begonnen = page.waitForResponse('**/api/auth/passkey/register/begin');
		const karte = page.getByTestId('passkeys-card');
		await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
		await page.getByTestId('passkey-label-input').fill(LABEL_FRISCH);
		const bestaetigen = page.getByTestId('passkey-create-confirm');
		await bestaetigen.click();

		await begonnen;
		const zeremonieStart = Date.now();
		const warten = page.getByTestId('passkey-create-pending');
		await expect(warten, 'der Wartezustand steht gar nicht — es läuft keine Zeremonie').toBeVisible();

		// 1) Escape waehrend der laufenden Zeremonie.
		await page.keyboard.press('Escape');
		expect(
			await dialogVerschwindet(),
			'Escape schließt den Dialog, obwohl die Bestätigung am Gerät noch aussteht'
		).toBe(false);
		await expect(warten, 'nach Escape ist der Wartezustand verschwunden').toBeVisible();

		// 2) Klick auf die Flaeche neben dem Dialog (Overlay).
		const overlay = page.locator('[data-slot="dialog-overlay"]');
		await expect(overlay, 'kein Overlay hinter dem Dialog gefunden').toBeVisible();
		await overlay.click({ position: { x: 5, y: 5 } });
		expect(
			await dialogVerschwindet(),
			'der Klick neben den Dialog schließt ihn, obwohl die Bestätigung am Gerät noch aussteht'
		).toBe(false);
		await expect(
			warten,
			'nach dem Klick neben den Dialog ist der Wartezustand verschwunden'
		).toBeVisible();

		// 3) Das X in der Ecke des Dialogs. Es darf waehrend der Zeremonie gar
		// nicht erst dastehen — ein sichtbares X, das nichts tut, waere fuer den
		// Nutzer genauso irrefuehrend wie eines, das den Dialog wegnimmt.
		const xKnopf = page.locator('[data-slot="dialog-content"] [data-slot="dialog-close"]');
		const xAnzahl = await xKnopf.count();
		if (xAnzahl > 0) {
			await xKnopf.first().click();
			expect(
				await dialogVerschwindet(),
				'das X schließt den Dialog, obwohl die Bestätigung am Gerät noch aussteht'
			).toBe(false);
			await expect(warten, 'nach dem Klick auf das X ist der Wartezustand verschwunden').toBeVisible();
		}

		// Beleg, dass alle Messungen MITTENDRIN lagen: noch keine Meldung da …
		await expect(
			page.getByTestId('passkey-error'),
			'zum Messzeitpunkt lag bereits ein Ergebnis vor — geprüft wurde also nicht die laufende Zeremonie'
		).toHaveCount(0);
		// … und die Frist der Zeremonie war noch nicht abgelaufen.
		expect(
			Date.now() - zeremonieStart,
			'die Messungen fielen hinter das Ende der Zeremonie — der Schutz wurde nicht belegt'
		).toBeLessThan(FRIST_MS);

		// Nach dem Ende der Zeremonie geht der Dialog zu — der Schutz haelt ihn
		// nicht dauerhaft fest.
		await expect(
			page.getByTestId('passkey-error'),
			'die beendete Zeremonie bleibt ohne Rückmeldung'
		).toBeVisible({ timeout: 30_000 });
		await expect(
			bestaetigen,
			'der Dialog bleibt nach der beendeten Zeremonie offen stehen'
		).toBeHidden();
	});

	// -------------------------------------------------------------------
	// F003 (Adversary #2246): die Spec verlangt einen neutralen Platzhalter,
	// wenn WEDER Label NOCH Geraetename vorhanden sind. Alle uebrigen Tests
	// vergeben ein Label, der Zweig wird nie erreicht. Hier bleibt das Feld
	// leer; dass auch der Geraetename fehlt (Null-AAGUID des virtuellen
	// Authentifikators), wird am Server nachgemessen — sonst wuesste der Test
	// nicht, welchen der drei Faelle er misst.
	// -------------------------------------------------------------------
	test('F003: ein Passkey ohne Bezeichnung zeigt einen neutralen Platzhalter statt einer leeren Zeile', async ({
		page
	}) => {
		await page.goto('/account');

		// Anlegen OHNE Bezeichnung: Feld bleibt leer.
		const karte = page.getByTestId('passkeys-card');
		await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
		const eingabe = page.getByTestId('passkey-label-input');
		await expect(
			eingabe,
			'die Bezeichnung ist nicht leer — der Platzhalter-Fall entsteht so nicht'
		).toHaveValue('');
		await page.getByTestId('passkey-create-confirm').click();

		const zeile = karte.getByTestId('passkey-row');
		await expect(zeile, 'der Passkey ohne Bezeichnung erscheint nicht in der Liste').toHaveCount(1);

		// Messgrundlage: der Server fuehrt weder Label noch Geraetename — nur so
		// ist belegt, dass die Zeile wirklich den dritten Fall zeigt.
		const vomServer = await serverPasskeys(page);
		expect(vomServer.length).toBe(1);
		expect(
			(vomServer[0].label ?? '').trim(),
			'der Server führt doch eine Bezeichnung — gemessen wird dann nicht der Platzhalter-Fall'
		).toBe('');
		expect(
			(vomServer[0].authenticator_name ?? '').trim(),
			'der Server liefert einen Gerätenamen — gemessen wird dann nicht der Platzhalter-Fall'
		).toBe('');

		// Die Zeile darf nicht namenlos bleiben.
		const titel = zeile.locator('span').first();
		await expect(titel, 'die Zeile zeigt keine sichtbare Bezeichnung').toBeVisible();
		const text = (await titel.innerText()).trim();
		expect(
			text.length,
			`die Zeile des namenlosen Passkeys hat keine Bezeichnung ("${text}")`
		).toBeGreaterThanOrEqual(3);
		// Rohwerte statt Text: entweder steht dort NUR ein Platzhalterwort der
		// Sprache — oder ein durchgereichtes Objekt/undefined mitten im Satz.
		expect(text.toLowerCase(), `die Bezeichnung ist ein Rohwert ("${text}")`).not.toMatch(
			/^(undefined|null|nan)$/
		);
		expect(text, `die Bezeichnung enthält einen Rohwert ("${text}")`).not.toMatch(
			/undefined|\[object/i
		);
		expect(
			text,
			`an der Stelle der Bezeichnung steht das Anlagedatum ("${text}") statt eines Platzhalters`
		).not.toMatch(/^Angelegt am/);
		await expect(
			zeile,
			'in der Zeile steht ein Rohwert statt eines neutralen Platzhalters'
		).not.toContainText('undefined');
	});
});
