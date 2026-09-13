// TDD RED — Issue #2248 (Scheibe 3 von #2199): einmaliges, geraeteuebergreifend
// abweisbares Passkey-Angebot.
// Spec: docs/specs/modules/passkey_angebot_banner.md — AC-1 bis AC-5.
// (AC-6 liegt in internal/handler/profile_passkey_prompt_test.go, AC-7/AC-8 in
//  frontend/src/lib/passkeyAngebot.test.ts — beide in der CI-Ampel.)
//
// Diese Spec wird bewusst NICHT in .github/ci_e2e_specs.txt aufgenommen (Spec,
// "Known Limitations"): passkey-login.spec.ts aus Scheibe 2 steht dort
// ebenfalls nicht, und ein CDP-Virtual-Authenticator-Test in der Ampel waere
// eine Flake-Haftung auf `main`. Ihr Nachweis entsteht in /e2e-verify.
//
// Heute ist jeder Testfall rot: das Banner existiert nicht (kein
// data-testid="passkey-angebot" in +layout.svelte), der Anmelde-Marker wird
// nicht gesetzt und `passkey_prompt_dismissed` kennt das Profil nicht.
//
// ---------------------------------------------------------------------
// UI-Vertrag, den die Implementierung erfuellen muss (RED legt ihn fest,
// Muster passkey-login.spec.ts:13-25):
//   [data-testid="passkey-angebot"]   das Banner, role="status", ausserhalb
//                                     des Chrome-Blocks (#2128)
//   darin zwei Knoepfe, adressiert ueber ihre Beschriftung aus der Spec:
//     "Jetzt einrichten"  ruft registerPasskey(label)
//     "Nicht jetzt"       schickt PUT /api/auth/profile mit AUSSCHLIESSLICH
//                         { passkey_prompt_dismissed: true }
//   Konto-Karte (Scheibe 1, #2246) unveraendert wiederverwendet:
//     [data-testid="passkeys-card"], "Passkey hinzufügen",
//     [data-testid="passkey-label-input"], [data-testid="passkey-create-confirm"],
//     [data-testid="passkey-row"]
//
// ---------------------------------------------------------------------
// ZWEI ANGRIFFSPUNKTE, die diese Datei bewusst anders loest als naheliegend:
//
// 1. AC-3 ist der tragende Nachweis fuer "serverseitig gemerkt, nicht im
//    Geraetespeicher". Damit er etwas MISST, muss in Kontext B alles auf
//    "zeigen" stehen: frische Passwort-Anmeldung (erzeugt einen frischen
//    Marker), leerer Geraetespeicher, derselbe Nutzer ohne Passkey. Nur der
//    serverseitig gemerkte Vermerk darf das Banner dort unterdruecken.
//    `browser.newContext({ storageState: undefined })` — das `undefined` ist
//    Pflicht (Muster compare-cross-user-write-block.spec.ts:43-65): ohne es
//    erbt der Kontext die Projekt-Default-storageState (admin.json) und waere
//    bereits als fremder Nutzer angemeldet. Ohne die Neuanmeldung in B faehrt
//    der Test in einem Kontext ohne Marker — dann fehlte das Banner auch bei
//    einer localStorage-Implementierung, und der Test bewachte nichts.
//
// 2. Kein `toBeVisible()` als einziger Sichtbarkeits-Nachweis: ein
//    ueberdecktes Element gilt fuer Playwright weiterhin als sichtbar, und ein
//    Desktop-Viewport macht Handy-Fehler unsichtbar. Darum laeuft jeder
//    Testfall im Handy-Viewport, und AC-2 klickt den Knopf wirklich und
//    beobachtet den ausgeloesten PUT — ein Klick, der ankommt, ist der
//    haertere Erreichbarkeits-Nachweis als jede Sichtbarkeits-Zusicherung.
//
// ---------------------------------------------------------------------
// BEKANNTE GRENZE von AC-2 (offen ausgesprochen, nicht entdeckt): ob der
// Anmelde-Marker nach der Anzeige in der Adresse stehenbleibt, ist bewusst
// nicht entschieden (Kontext-Dokument, Risiko 5). Streift die Implementierung
// ihn ab, laedt `page.reload()` eine markerfreie Adresse — die
// Reload-Zusicherung waere dann trivial wahr. Der belastbare Nachweis fuer
// "serverseitig gemerkt" ist deshalb AC-3, so wie die Spec ihn auch zuweist.
// Hier wird nichts nachgeschaerft: eine Zusicherung auf die Adresse wuerde
// eine Entscheidung festschreiben, die niemand getroffen hat.
//
// ---------------------------------------------------------------------
// ANFRAGE-KONTINGENTE (Muster run-passkey-login.sh): /api/auth/register ist auf
// 5 Versuche pro IP und Stunde begrenzt (router.go:40), alle Passkey-Routen
// teilen 30 Anfragen pro Stunde (router.go:97). Diese Datei legt darum GENAU
// ZWEI Konten an und setzt den Zustand zwischen den Testfaellen zurueck, statt
// pro Testfall neu zu registrieren. Ein zweiter Lauf innerhalb derselben
// Stunde braucht trotzdem einen frischen Go-Server, sonst antwortet die
// Registrierung mit 429 — sichtbar als "Banner erscheint nicht" statt als
// Kontingent-Meldung.
//
// Ausfuehrung (aus frontend/, gegen den CI-Stack wie bei #2247):
//   npx playwright test e2e/passkey-angebot.spec.ts --project=tests

import { test, expect } from '@playwright/test';
import type { APIRequestContext, BrowserContext, CDPSession, Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

const HANDY = { width: 375, height: 812 };
const BANNER = 'passkey-angebot';
const EINRICHTEN = 'Jetzt einrichten';
const NICHT_JETZT = 'Nicht jetzt';
const LABEL = 'E2E-GZ-2248-Angebot';
const PASSWORT = 'test1234';

/** CDP-Antwort von WebAuthn.addVirtualAuthenticator. */
type VirtuellerAuthenticator = { authenticatorId: string };

/**
 * Haengt einen virtuellen Authentifikator an die Seite — echte Zeremonie ohne
 * Geraet (Muster passkey-login.spec.ts:273-275, dort selbst schon eine Kopie
 * aus passkey-regression.spec.ts; ein geteilter Helfer beruehrte fremde,
 * heute gruene Specs).
 */
async function virtuellerAuthenticator(context: BrowserContext, page: Page): Promise<CDPSession> {
	const cdp = await context.newCDPSession(page);
	await cdp.send('WebAuthn.enable');
	(await cdp.send('WebAuthn.addVirtualAuthenticator', {
		options: {
			protocol: 'ctap2',
			transport: 'internal',
			hasResidentKey: true,
			hasUserVerification: true,
			isUserVerified: true,
			automaticPresenceSimulation: true
		}
	})) as unknown as VirtuellerAuthenticator;
	return cdp;
}

/**
 * Legt ein Konto an und macht seine Adresse bestaetigt.
 *
 * Die Bestaetigung ist nach #2271 (Anmeldung nur mit bestaetigter Adresse)
 * noetig, und auf Staging kann die Bestaetigungsmail strukturell nicht
 * zugestellt werden (Egress-Sperre #1337). Den Weg dafuer liefert #2304:
 * POST /api/auth/verify-email/staging-token gibt das Token heraus, eingeloest
 * wird es ueber den echten Produktionspfad POST /api/auth/verify-email. Der
 * Token-Weg ist anmeldepflichtig — deshalb erst anmelden, dann bestaetigen.
 *
 * Bewusst nachsichtig: liefert der Token-Weg 404 (Stand ohne GZ_ENV=staging,
 * z.B. der lokale CI-Stack), laeuft der Nachweis weiter — solange die
 * Login-Pflicht nicht scharf ist, braucht er die Bestaetigung nicht.
 */
async function legeKontoAn(request: APIRequestContext, name: string): Promise<void> {
	const reg = await request.post('/api/auth/register', {
		data: { username: name, password: PASSWORT, email: `${name}@example.com` }
	});
	expect(
		[200, 201].includes(reg.status()),
		`Registrierung ${name} fehlgeschlagen: ${reg.status()} ${await reg.text()} ` +
			'(429 = Kontingent 5/Stunde erschoepft, frischen Go-Server nehmen)'
	).toBeTruthy();

	const login = await request.post('/api/auth/login', {
		data: { username: name, password: PASSWORT }
	});
	if (!login.ok()) return; // Login-Pflicht schon scharf: Token-Weg unerreichbar.

	const tokenAntwort = await request.post('/api/auth/verify-email/staging-token', {
		data: { username: name }
	});
	if (!tokenAntwort.ok()) return; // Kein Staging-Stand — Bestaetigung nicht noetig.
	const { token } = (await tokenAntwort.json()) as { token: string };
	const verify = await request.post('/api/auth/verify-email', { data: { user: name, token } });
	expect(verify.ok(), `Bestaetigung ${name} fehlgeschlagen: ${verify.status()}`).toBeTruthy();
}

/**
 * Setzt das Konto auf "Angebot faellig" zurueck: Abweisung geloescht, alle
 * E2E-Passkeys entfernt. Damit ist jeder Testfall unabhaengig von der
 * Reihenfolge, ohne ein neues Konto zu verbrauchen.
 *
 * Die Vorbedingung wird anschliessend GELESEN, nicht angenommen — misslingt
 * der Ruecksetzer still, fehlte das Banner spaeter aus dem falschen Grund und
 * der Testfall waere aus dem falschen Grund rot.
 */
async function setzeAngebotZurueck(request: APIRequestContext): Promise<void> {
	await request.put('/api/auth/profile', { data: { passkey_prompt_dismissed: false } });

	const profil = await request.get('/api/auth/profile');
	expect(profil.ok(), `Profil nicht lesbar: ${profil.status()}`).toBeTruthy();
	const daten = (await profil.json()) as {
		passkey_prompt_dismissed?: boolean;
		passkeys?: { id: string; label?: string }[];
	};
	for (const pk of daten.passkeys ?? []) {
		await request.delete(`/api/auth/passkey/credentials/${encodeURIComponent(pk.id)}`);
	}

	const nachher = await (await request.get('/api/auth/profile')).json();
	expect(
		nachher.passkey_prompt_dismissed ?? false,
		'Vorbedingung: die Abweisung liess sich nicht zuruecknehmen — ein fehlendes Banner ' +
			'bewiese danach nichts'
	).toBeFalsy();
	expect(
		nachher.has_passkey,
		'Vorbedingung: es liegt noch ein Passkey — das Angebot waere zu Recht unsichtbar'
	).toBeFalsy();
}

/** Meldet sich ueber das Passwort-Formular an — nur dieser Weg setzt den Marker. */
async function meldePasswortAn(page: Page, name: string): Promise<void> {
	await page.goto('/login');
	await page.fill('input[name="username"]', name);
	await page.fill('input[name="password"]', PASSWORT);
	await page.click('button[type="submit"]');
	await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15_000 });
}

/** Legt ueber die Konto-Karte (#2246) einen echten Passkey an. */
async function legePasskeyUeberKontoAn(page: Page, label: string): Promise<void> {
	await page.goto('/account');
	const karte = page.getByTestId('passkeys-card');
	await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
	await page.getByTestId('passkey-label-input').fill(label);
	await page.getByTestId('passkey-create-confirm').click();
	await expect(karte.getByTestId('passkey-row').filter({ hasText: label })).toBeVisible({
		timeout: 15_000
	});
}

const stempel = Date.now();
const basisNutzer = `e2e2248a${stempel}`;
const passkeyNutzer = `e2e2248b${stempel}`;

test.describe('Issue #2248 — Passkey-Angebot nach Passwort-Anmeldung', () => {
	test.use({ viewport: HANDY });

	test.beforeAll(async ({ browser }) => {
		const ctx = await browser.newContext({ storageState: undefined });
		await legeKontoAn(ctx.request, basisNutzer);
		await legeKontoAn(ctx.request, passkeyNutzer);
		await ctx.close();
	});

	test.beforeEach(async ({ page, context, baseURL }) => {
		assertNotProdBaseURL(baseURL ?? '');
		// Die Projekt-Default-storageState (admin.json) waere ein fremder
		// Nutzer — jeder Testfall meldet sich selbst neu an.
		await context.clearCookies();
		await page.addInitScript(() => {
			try {
				window.localStorage.clear();
			} catch {
				/* ohne Speicherzugriff ist nichts zu leeren */
			}
		});
	});

	// ── AC-1 ───────────────────────────────────────────────────────────────────
	test('AC-1: Passwort-Login ohne Passkey zeigt das Banner mit beiden Aktionen', async ({
		page,
		context
	}) => {
		await meldePasswortAn(page, basisNutzer);
		await setzeAngebotZurueck(context.request);
		await meldePasswortAn(page, basisNutzer);

		const banner = page.getByTestId(BANNER);
		await expect(banner).toBeVisible({ timeout: 15_000 });
		await expect(banner).toHaveAttribute('role', 'status');
		await expect(banner.getByRole('button', { name: EINRICHTEN })).toBeVisible();
		await expect(banner.getByRole('button', { name: NICHT_JETZT })).toBeVisible();
	});

	// ── AC-2 ───────────────────────────────────────────────────────────────────
	test('AC-2: Klick auf "Nicht jetzt" blendet das Banner aus, Reload zeigt es nicht erneut', async ({
		page,
		context
	}) => {
		await meldePasswortAn(page, basisNutzer);
		await setzeAngebotZurueck(context.request);
		await meldePasswortAn(page, basisNutzer);

		const banner = page.getByTestId(BANNER);
		await expect(banner).toBeVisible({ timeout: 15_000 });

		// Nutzlast-Disziplin (Spec, "Aktionen"): AUSSCHLIESSLICH das eigene
		// Feld. Kaeme ein abweichender email/mail_to-Wert mit, setzte
		// auth.go:706-715 email_verified_at zurueck — nach #2271 eine
		// Aussperr-Falle. Darum wird die Nutzlast hier mitgelesen.
		const putAnfrage = page.waitForRequest(
			(req) => req.method() === 'PUT' && req.url().includes('/api/auth/profile'),
			{ timeout: 15_000 }
		);
		await banner.getByRole('button', { name: NICHT_JETZT }).click();
		const nutzlast = JSON.parse((await putAnfrage).postData() ?? '{}');

		expect(
			nutzlast.passkey_prompt_dismissed,
			`PUT-Nutzlast setzt die Abweisung nicht: ${JSON.stringify(nutzlast)}`
		).toBe(true);
		expect(
			Object.keys(nutzlast).sort(),
			'die Nutzlast enthaelt mehr als das eigene Feld — jeder abweichende ' +
				'email/mail_to-Wert setzt die Adress-Bestaetigung zurueck (#2271)'
		).toEqual(['passkey_prompt_dismissed']);

		// Sofort weg, ohne auf einen neuen Ladelauf zu warten.
		await expect(banner).toHaveCount(0, { timeout: 5_000 });

		// Und nach dem Neuladen derselben Seite bleibt es weg.
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId(BANNER)).toHaveCount(0);
	});

	// ── AC-3 — der tragende Nachweis ───────────────────────────────────────────
	test('AC-3: zweiter Browser-Kontext mit derselben Anmeldung zeigt das Banner nicht erneut', async ({
		page,
		context,
		browser
	}) => {
		// Kontext A: Angebot faellig machen, sehen, abweisen.
		await meldePasswortAn(page, basisNutzer);
		await setzeAngebotZurueck(context.request);
		await meldePasswortAn(page, basisNutzer);

		const bannerA = page.getByTestId(BANNER);
		await expect(
			bannerA,
			'Positivkontrolle: ohne sichtbares Banner in Kontext A gibt es nichts abzuweisen ' +
				'und der Nachweis unten waere leer'
		).toBeVisible({ timeout: 15_000 });
		await bannerA.getByRole('button', { name: NICHT_JETZT }).click();
		await expect(bannerA).toHaveCount(0, { timeout: 5_000 });

		// Kontext B: frisches Geraet. `storageState: undefined` ist Pflicht,
		// sonst erbt B die Projekt-Default-Anmeldung (admin.json) und meldete
		// einen fremden Nutzer an.
		const ctxB = await browser.newContext({ storageState: undefined, viewport: HANDY });
		try {
			const pageB = await ctxB.newPage();
			await pageB.addInitScript(() => {
				try {
					window.localStorage.clear();
				} catch {
					/* ohne Speicherzugriff ist nichts zu leeren */
				}
			});

			// Frische Passwort-Anmeldung ⇒ frischer Marker. Ohne sie faehrt B
			// ohne Marker, und das Banner fehlte auch bei einer reinen
			// localStorage-Loesung — der Test wuerde nichts messen.
			await meldePasswortAn(pageB, basisNutzer);

			// Gegenprobe, dass in B wirklich ALLES auf "zeigen" steht und nur
			// der serverseitige Vermerk bremst.
			const profilB = await (await ctxB.request.get('/api/auth/profile')).json();
			expect(profilB.has_passkey, 'Kontext B: Nutzer hat einen Passkey — falscher Grund').toBeFalsy();
			expect(
				profilB.passkey_prompt_dismissed,
				'Kontext B: der Server hat die Abweisung nicht gemerkt — sie haengt am Geraetespeicher'
			).toBe(true);
			const speicherB = await pageB.evaluate(() => ({ laenge: window.localStorage.length }));
			expect(
				speicherB.laenge,
				'Kontext B: der Geraetespeicher ist nicht leer — das Banner koennte aus dem ' +
					'falschen Grund fehlen'
			).toBe(0);

			await pageB.waitForLoadState('networkidle');
			await expect(pageB.getByTestId(BANNER)).toHaveCount(0);
		} finally {
			await ctxB.close();
		}
	});

	// ── AC-4 ───────────────────────────────────────────────────────────────────
	test('AC-4: Passwort-Login mit vorhandenem Passkey zeigt das Banner nie', async ({
		page,
		context
	}) => {
		await virtuellerAuthenticator(context, page);
		await meldePasswortAn(page, passkeyNutzer);
		await setzeAngebotZurueck(context.request);
		// Der Sprung auf /account laesst den Anmelde-Marker fallen — deshalb
		// steht hier waehrend der Passkey-Anlage kein Banner im Weg. Das ist
		// load-bearing: wuerde die Anlage aus der markierten Adresse heraus
		// laufen, koennte das Banner den passkey-create-confirm-Klick
		// abfangen, sichtbar nur als raetselhafter Timeout.
		await legePasskeyUeberKontoAn(page, `${LABEL}-AC4`);

		// Frische Anmeldung: Marker gesetzt, Abweisung nicht gesetzt —
		// einzig der vorhandene Passkey darf das Angebot verhindern.
		await meldePasswortAn(page, passkeyNutzer);
		const profil = await (await context.request.get('/api/auth/profile')).json();
		expect(profil.has_passkey, 'Vorbedingung: der Passkey wurde nicht angelegt').toBe(true);
		expect(
			profil.passkey_prompt_dismissed ?? false,
			'Vorbedingung: die Abweisung steht — dann bewiese ein fehlendes Banner nichts'
		).toBeFalsy();

		// Diese eine Zusicherung traegt AC-4 allein — und zwar genau HIER, bei
		// gesetztem Marker. Ein zweiter Blick auf einer nachnavigierten Seite
		// (z.B. /trips) waere wertlos: dort ist der Marker weg, also fehlte
		// das Banner auch bei einer Implementierung, die hasPasskey gar nicht
		// beachtet. "Stellt sich von selbst ein" ist keine Bewachung.
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId(BANNER)).toHaveCount(0);
	});

	// ── AC-5 ───────────────────────────────────────────────────────────────────
	test('AC-5: erfolgreiche Passkey-Registrierung ueber das Banner laesst es verschwinden', async ({
		page,
		context
	}) => {
		await virtuellerAuthenticator(context, page);
		await meldePasswortAn(page, basisNutzer);
		await setzeAngebotZurueck(context.request);
		await meldePasswortAn(page, basisNutzer);

		const banner = page.getByTestId(BANNER);
		await expect(banner).toBeVisible({ timeout: 15_000 });

		await banner.getByRole('button', { name: EINRICHTEN }).click();

		// Das Banner blendet sich SELBST aus, sobald die Zeremonie durch ist —
		// der serverseitig geladene has_passkey-Wert ist in diesem Moment
		// veraltet und saegte das Angebot sonst nicht ab (Spec, "Aktionen").
		await expect(banner).toHaveCount(0, { timeout: 20_000 });

		// Und die Zeremonie ist wirklich durchgelaufen — sonst waere das
		// Verschwinden bloss ein Fehlerzweig.
		const profil = await (await context.request.get('/api/auth/profile')).json();
		expect(
			profil.has_passkey,
			'das Banner ist verschwunden, aber es liegt kein Passkey — es hat sich bei einem ' +
				'FEHLSCHLAG ausgeblendet statt bei Erfolg'
		).toBe(true);
		expect(
			profil.passkey_prompt_dismissed ?? false,
			'"Jetzt einrichten" darf die Abweisung nicht setzen — das ist die Aufgabe von ' +
				`"${NICHT_JETZT}"`
		).toBeFalsy();
	});
});
