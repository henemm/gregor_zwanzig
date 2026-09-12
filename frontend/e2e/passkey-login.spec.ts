// TDD RED — Issue #2247 (Scheibe 2 von #2199).
// Spec: docs/specs/modules/passkey_login_anordnung.md — AC-1, AC-2, AC-5 bis AC-10.
// (AC-3, AC-4-positiv, AC-11 laufen im SSR-Test:
//  src/routes/login/__tests__/login_erstes_bild.test.ts — siehe dort, warum
//  AC-4s Negativ-Zweig NICHT im SSR-Test steht.)
//
// Oberflaechen-Nachweis im echten Browser: /login hat heute kein einziges
// Wort "passkey" (Spec, Abschnitt "Source") — jeder Test hier ist darum
// heute rot, weil weder der Knopf noch der Hinweistext noch die
// Order-Umsortierung existieren.
//
// ---------------------------------------------------------------------
// UI-Vertrag, den die Implementierung erfuellen muss (RED legt ihn fest,
// analog zum Vertrags-Kommentar in passkey-konto.spec.ts):
//   [data-testid="login-passkey-btn"]    Knopf (Spec/Kontext-Dokument, verbindlich)
//   [data-testid="login-passkey-area"]   Container mit FESTER Hoehe ueber alle
//                                        drei Zustaende (Implementation Details,
//                                        "fester Container statt Text kurz halten")
//   [data-testid="login-passkey-hint"]   Hinweistext ohne WebAuthn-Unterstuetzung
//   [data-testid="login-passkey-error"]  deutsche Fehlermeldung (Abbruch/Zeitueberschreitung)
//   Passwort-Form bleibt ueber `form` ansprechbar (einziges Formular auf der
//   Seite, kein neuer Testid noetig) — ebenso Google (`a[href="/api/auth/google/init"]`)
//   und Magic-Link (`a[href="/magic-link"]`), beide existieren schon heute.
//
// AC-9 (entschieden, PO-Korrektur nach Rueckfrage): WebAuthn meldet Abbruch,
// Zeitueberschreitung und "kein passender Passkey" ABSICHTLICH als
// denselben Fehler (NotAllowedError) -- Privacy-Design, damit eine Webseite
// nicht unterscheiden kann, ob der Nutzer abgelehnt hat oder ob gar kein
// Passkey vorhanden war. Die Anmeldeseite hat also gar keine Information,
// aus der sie zwei verschiedene Texte ableiten koennte; der TimeoutError-
// Zweig im alten Stand c09172f5 war aus demselben Grund toter Code ("nie
// getestet, nie funktioniert"). AC-9 verlangt darum NUR NOCH EINE
// verstaendliche deutsche Fehlermeldung, gleich ueber welchen der beiden
// Wege sie entsteht -- gleicher Text in beiden Faellen ist ausdruecklich
// erlaubt. Die zwei Testfaelle unten bleiben trotzdem beide bestehen, weil
// sie zwei verschiedene reale Fehlschlag-Wege durchspielen (kein
// Authentifikator vorhanden · Authentifikator vorhanden aber ohne
// Praesenzbestaetigung + verkuerzte Frist) -- nur die Zusicherung ist jetzt
// "eine nicht-leere deutsche Meldung je Weg", nicht mehr "zwei
// unterscheidbare Meldungen".
//
// Pflicht-Vorspann Issue #1265: assertNotProdBaseURL in jedem Testfall.
// Kein geteilter Helper fuer den virtuellen Authentifikator (Aufsatz aus
// passkey-regression.spec.ts:55-74, hier ein drittes Mal kopiert) — ein
// Helper beruehrte zwei heute gruene Specs, ausserhalb dieses Tickets.
//
// Ausfuehrung: siehe run-passkey-login.sh (Rate-Limit-Aufteilung).

import { test, expect } from '@playwright/test';
import type { BrowserContext, CDPSession, Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

const MOBILE = { width: 375, height: 812 };
const DESKTOP = { width: 1280, height: 800 };
const LABEL = 'E2E-GZ-2247-Login';
// Eigener Stamm fuer die AC-9-Passkeys: LABEL darf NICHT sein Praefix sein,
// sonst trifft AC-7s `hasText: LABEL` diese Zeilen mit und wird mehrdeutig.
const LABEL_FEHLSCHLAG = 'E2E-GZ-2247-Fehlschlag';

/** CDP-Antwort von WebAuthn.addVirtualAuthenticator. */
type VirtuellerAuthenticator = { authenticatorId: string };

/** Sitzungskekse, wie `context.cookies()` sie liefert und `addCookies` sie nimmt. */
type Sitzungskekse = Parameters<BrowserContext['addCookies']>[0];

test.describe('Passkey-Login-Anordnung (#2247)', () => {
	test.beforeEach(async ({ baseURL }) => {
		// Issue #1265: niemals gegen Produktion.
		assertNotProdBaseURL(baseURL ?? '');
	});

	// ── AC-1/AC-2: tatsaechliche Bildschirmposition, nicht Dokumentreihenfolge ──
	test.describe('AC-1/AC-2: Positionsvergleich Handy/Desktop', () => {
		test('AC-1: @375px steht der Passkey-Weg oberhalb des Passwort-Formulars', async ({
			page,
			context
		}) => {
			await context.clearCookies();
			await page.setViewportSize(MOBILE);
			await page.goto('/login');

			const rect = await page.evaluate(() => {
				const area = document.querySelector('[data-testid="login-passkey-area"]');
				const form = document.querySelector('form');
				return {
					areaTop: area ? area.getBoundingClientRect().top : null,
					formTop: form ? form.getBoundingClientRect().top : null
				};
			});
			expect(rect.areaTop, 'login-passkey-area fehlt im DOM').not.toBeNull();
			expect(rect.formTop, 'Passwort-Formular fehlt im DOM').not.toBeNull();
			expect(
				rect.areaTop as number,
				`Passkey-Bereich (top=${rect.areaTop}) liegt bei 375px nicht oberhalb des ` +
					`Passwort-Formulars (top=${rect.formTop})`
			).toBeLessThan(rect.formTop as number);
		});

		test('AC-2: @1280px steht der Passkey-Weg unterhalb des Passwort-Formulars', async ({
			page,
			context
		}) => {
			await context.clearCookies();
			await page.setViewportSize(DESKTOP);
			await page.goto('/login');

			const rect = await page.evaluate(() => {
				const area = document.querySelector('[data-testid="login-passkey-area"]');
				const form = document.querySelector('form');
				return {
					areaTop: area ? area.getBoundingClientRect().top : null,
					formBottom: form ? form.getBoundingClientRect().bottom : null
				};
			});
			expect(rect.areaTop, 'login-passkey-area fehlt im DOM').not.toBeNull();
			expect(rect.formBottom, 'Passwort-Formular fehlt im DOM').not.toBeNull();
			expect(
				rect.areaTop as number,
				`Passkey-Bereich (top=${rect.areaTop}) liegt bei 1280px nicht unterhalb des ` +
					`Passwort-Formulars (bottom=${rect.formBottom})`
			).toBeGreaterThanOrEqual(rect.formBottom as number);
		});
	});

	// ── AC-5/AC-6: Geraet ohne WebAuthn-Unterstuetzung ─────────────────────────
	test.describe('AC-5/AC-6: Ohne WebAuthn-Faehigkeit', () => {
		async function ohneWebAuthnLaden(page: Page): Promise<void> {
			// Erzwingt real den `false`-Zweig -- die einzige Stelle in dieser Scheibe,
			// an der die Faehigkeitspruefung echt im Browser ablaeuft (SSR hat nie
			// `window`, siehe login_erstes_bild.test.ts).
			await page.addInitScript(() => {
				// @ts-expect-error -- bewusst entfernt, um "kein WebAuthn" zu simulieren
				delete window.PublicKeyCredential;
			});
			await page.goto('/login');
		}

		test('AC-5: Hinweistext statt Knopf, Passwort-Weg bleibt bedienbar', async ({
			page,
			context
		}) => {
			await context.clearCookies();
			await ohneWebAuthnLaden(page);

			await expect(page.getByTestId('login-passkey-btn')).toHaveCount(0);
			const hinweis = page.getByTestId('login-passkey-hint');
			await expect(hinweis).toBeVisible();
			const text = (await hinweis.innerText()).trim();
			expect(text.length, `Hinweistext sagt nichts ("${text}")`).toBeGreaterThanOrEqual(10);

			await page.fill('input[name="username"]', 'irrelevant');
			await page.fill('input[name="password"]', 'irrelevant');
			await expect(page.locator('button[type="submit"]')).toBeEnabled();
		});

		test('AC-6: Passkey-Bereich ist in allen Zustaenden gleich hoch', async ({
			page,
			context
		}) => {
			await context.clearCookies();
			await page.goto('/login');
			const hoeheMitKnopf = await page.evaluate(() => {
				const el = document.querySelector('[data-testid="login-passkey-area"]');
				if (!el) throw new Error('login-passkey-area nicht gefunden (Knopf-Zustand)');
				return el.getBoundingClientRect().height;
			});

			await ohneWebAuthnLaden(page);
			const hoeheOhneWebAuthn = await page.evaluate(() => {
				const el = document.querySelector('[data-testid="login-passkey-area"]');
				if (!el) throw new Error('login-passkey-area nicht gefunden (Hinweis-Zustand)');
				return el.getBoundingClientRect().height;
			});

			expect(
				hoeheOhneWebAuthn,
				`Hoehe weicht ab -- mit Knopf ${hoeheMitKnopf}px, ohne WebAuthn ${hoeheOhneWebAuthn}px. ` +
					'Ein Hoehenunterschied verschiebt Benutzername/Passwort/Google/Magic-Link beim ' +
					'Zustandswechsel (Spec, "Hinweistext ohne WebAuthn").'
			).toBeCloseTo(hoeheMitKnopf, 0);
		});
	});

	// ── AC-8: Passwort/Google/Magic-Link bleiben SICHTBAR, nicht nur im DOM ────
	test('AC-8: Passwort, Google und Magic-Link ohne Scrollen erreichbar (375/1280px)', async ({
		page,
		context
	}) => {
		for (const vp of [MOBILE, DESKTOP]) {
			await context.clearCookies();
			await page.setViewportSize(vp);
			await page.goto('/login');

			const googleVorhanden = (await page.locator('a[href="/api/auth/google/init"]').count()) > 0;

			const sichtbar = await page.evaluate(() => {
				function imSichtbereich(sel: string): boolean {
					const el = document.querySelector(sel);
					if (!el) return false;
					const r = el.getBoundingClientRect();
					return r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0 && r.height > 0;
				}
				return {
					form: imSichtbereich('form'),
					google: imSichtbereich('a[href="/api/auth/google/init"]'),
					magicLink: imSichtbereich('a[href="/magic-link"]')
				};
			});

			expect(sichtbar.form, `Passwort-Form ausserhalb des Viewports bei ${vp.width}px`).toBe(true);
			expect(
				sichtbar.magicLink,
				`Magic-Link ausserhalb des Viewports bei ${vp.width}px`
			).toBe(true);
			if (googleVorhanden) {
				expect(
					sichtbar.google,
					`Google-Anmeldung ausserhalb des Viewports bei ${vp.width}px`
				).toBe(true);
			}
		}
	});

	// ── AC-10: Klick bei leerem Benutzernamen ───────────────────────────────────
	test('AC-10: Klick bei leerem Feld fokussiert Benutzername, bricht die Autofill-Anbindung NICHT ab', async ({
		page,
		context
	}) => {
		await context.clearCookies();

		let discoverableBeginAufrufe = 0;
		page.on('request', (req) => {
			if (req.url().includes('/api/auth/passkey/discoverable/begin')) discoverableBeginAufrufe++;
		});

		await page.goto('/login');
		await page.getByTestId('login-passkey-btn').waitFor({ state: 'visible' });
		// Zeitfenster fuer den anfaenglichen Conditional-UI-Start (isConditionalMediationAvailable
		// + discoverable/begin), bevor gemessen wird.
		await page.waitForTimeout(1000);
		const aufrufeVorKlick = discoverableBeginAufrufe;

		await page.getByTestId('login-passkey-btn').click();

		const fokussiert = await page.evaluate(() => document.activeElement?.id ?? null);
		expect(fokussiert, 'Klick bei leerem Feld hat den Fokus nicht auf #username gesetzt').toBe(
			'username'
		);

		await page.waitForTimeout(1000);
		expect(
			discoverableBeginAufrufe,
			'Klick bei leerem Feld hat einen ZUSAETZLICHEN discoverable/begin ausgeloest -- die ' +
				'Autofill-Anbindung wurde abgebrochen und neu gestartet (verbraucht zusaetzliche ' +
				'Anfragen aus dem geteilten Passkey-Kontingent, Spec "Knopf bei leerem Benutzernamen ' +
				'bleibt bedienbar").'
		).toBe(aufrufeVorKlick);
	});

	// ── AC-7/AC-9: echte Zeremonie über virtuellen CDP-Authentifikator ─────────
	test.describe('AC-7/AC-9: echte Zeremonie', () => {
		let cdp: CDPSession;
		let authenticatorId = '';
		// Aufraeum-Auftrag des laufenden Testfalls. Wird im afterEach abgearbeitet,
		// NICHT am Testende: eine fehlgeschlagene Zusicherung bricht den Testkoerper
		// ab, und ein Aufraeumen dahinter liefe nie -- genau bei roten Laeufen
		// (Mutations-Gegenproben) sammelten sich sonst Passkeys an, bis AC-7s
		// Zeilenfilter nicht mehr eindeutig trifft.
		let angelegtesLabel = '';
		let sitzungskekse: Sitzungskekse = [];

		test.beforeEach(async ({ page, context }) => {
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
		});

		/**
		 * Legt ueber die Konto-Karte (Scheibe 1, #2246) einen echten Passkey fuer
		 * den Testbenutzer an.
		 *
		 * PFLICHT vor jedem AC-9-Fehlschlag (Befund 2026-09-11): ohne angelegten
		 * Passkey antwortet /api/auth/passkey/login/begin mit 401
		 * (internal/handler/passkey.go:179-183) -- die Zeremonie erreicht
		 * navigator.credentials.get() dann NIE, und der Test misst den
		 * SERVERSEITIGEN statt des geraeteseitigen Fehlschlags, den AC-9
		 * zusichert. Der NotAllowedError-Zweig der Anmeldeseite waere unbewacht.
		 */
		async function legePasskeyAn(page: Page, label: string): Promise<void> {
			await page.goto('/account');
			const karte = page.getByTestId('passkeys-card');
			await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
			await page.getByTestId('passkey-label-input').fill(label);
			await page.getByTestId('passkey-create-confirm').click();
			await expect(karte.getByTestId('passkey-row').filter({ hasText: label })).toBeVisible({
				timeout: 15_000
			});
			// Aufraeum-Auftrag hinterlegen, samt der Kekse, die ihn ausfuehren
			// koennen -- die Messung selbst laeuft gleich abgemeldet.
			angelegtesLabel = label;
			sitzungskekse = await page.context().cookies();
		}

		/**
		 * Raeumt die in einem AC-9-Testfall angelegten Passkeys wieder weg.
		 *
		 * Die Messung laeuft abgemeldet (clearCookies), zum Loeschen braucht es
		 * aber eine gueltige Sitzung. Statt sich neu anzumelden werden die zuvor
		 * gesicherten Kekse zurueckgelegt: eine zweite Anmeldung zoege ein Token
		 * aus dem Login-Limiter (internal/router/router.go:45) und verfaelschte
		 * die Kontingent-Rechnung, um die es in dieser Spec gerade geht.
		 */
		async function raeumePasskeyWeg(
			page: Page,
			kekse: Sitzungskekse,
			label: string
		): Promise<void> {
			await page.context().addCookies(kekse);
			const profil = await page.request.get('/api/auth/profile');
			if (profil.status() !== 200) return;
			const passkeys = ((await profil.json()).passkeys ?? []) as { id: string; label?: string }[];
			for (const pk of passkeys.filter((p) => p.label === label)) {
				await page.request
					.delete(`/api/auth/passkey/credentials/${encodeURIComponent(pk.id)}`)
					.catch(() => undefined);
			}
		}

		/**
		 * Kuerzt die Frist der Anmelde-Zeremonie auf `ms`.
		 *
		 * Die Frist sitzt IN `publicKey`: der Server antwortet mit
		 * {"publicKey": {...}} (internal/handler/passkey.go:198). Auf oberster
		 * Ebene waere `timeout` ein totes Feld.
		 *
		 * BEIDE AC-9-Wege brauchen das (gemessen 2026-09-11): ohne gekuerzte Frist
		 * wartet Chromium auch dann bis zum Server-Default, wenn gar kein
		 * Authentifikator mehr da ist -- AC-9a lief so in die 15-s-Schranke von
		 * Playwright und meldete "keine Fehlermeldung", obwohl die Anmeldeseite
		 * korrekt arbeitet. Die Frist ist der Ausloeser, nicht die Zusicherung:
		 * geprueft wird weiterhin der deutsche Text bei NotAllowedError.
		 */
		async function kuerzeZeremonieFrist(page: Page, ms: number): Promise<void> {
			await page.route('**/api/auth/passkey/login/begin', async (route) => {
				const antwort = await route.fetch();
				const koerper = await antwort.json();
				if (koerper.publicKey) koerper.publicKey.timeout = ms;
				await route.fulfill({ response: antwort, json: koerper });
			});
		}

		test.afterEach(async ({ page, context }) => {
			if (authenticatorId) {
				await cdp
					.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId })
					.catch(() => undefined);
				authenticatorId = '';
			}
			// Erst raeumen, DANN die Kekse loeschen -- das Loeschen braucht sie.
			if (angelegtesLabel) {
				await raeumePasskeyWeg(page, sitzungskekse, angelegtesLabel).catch(() => undefined);
				angelegtesLabel = '';
				sitzungskekse = [];
			}
			await context.clearCookies().catch(() => undefined);
		});

		test('AC-7: Anmeldung am echten Passkey-Knopf, ohne jede Passworteingabe', async ({
			page
		}) => {
			test.setTimeout(45_000);

			// Ausgangslage: Standard-storageState ist bereits angemeldet -- Passkey
			// ueber die Konto-Karte anlegen (Scheibe 1, #2246).
			await page.goto('/account');
			const karte = page.getByTestId('passkeys-card');
			await karte.getByRole('button', { name: 'Passkey hinzufügen' }).click();
			await page.getByTestId('passkey-label-input').fill(LABEL);
			await page.getByTestId('passkey-create-confirm').click();
			await expect(karte.getByTestId('passkey-row').filter({ hasText: LABEL })).toBeVisible({
				timeout: 15_000
			});

			const username = process.env.GZ_E2E_USER ?? 'admin';

			// Echt abmelden, damit die Zeremonie wirklich OHNE bestehende Sitzung
			// startet -- kein Passwortfeld wird in diesem Test je befuellt.
			await page.context().clearCookies();
			await page.goto('/login');

			await page.fill('#username', username);
			await page.getByTestId('login-passkey-btn').click();
			await page.waitForURL('/', { timeout: 15_000 });

			const profil = await page.request.get('/api/auth/profile');
			expect(profil.status(), 'nach der Passkey-Anmeldung ist keine Sitzung gueltig').toBe(200);

			// Aufraeumen: den in diesem Test angelegten Passkey wieder entfernen.
			const passkeys = ((await profil.json()).passkeys ?? []) as { id: string; label?: string }[];
			for (const pk of passkeys.filter((p) => p.label === LABEL)) {
				await page.request
					.delete(`/api/auth/passkey/credentials/${encodeURIComponent(pk.id)}`)
					.catch(() => undefined);
			}
		});

		test('AC-9a: Kein Authentifikator verfuegbar zeigt eine verstaendliche deutsche Fehlermeldung', async ({
			page,
			context
		}) => {
			test.setTimeout(45_000);
			// Echter Testbenutzer MIT Passkey -- sonst scheitert schon login/begin
			// am Server (401) und die Zeremonie erreicht das Geraet nie.
			// Label bewusst OHNE LABEL-Praefix: AC-7 sucht seine Zeile per
			// `hasText: LABEL`, und das trifft per Teilzeichenkette auch jedes
			// `${LABEL}-…` -- ein liegengebliebener Rest machte AC-7s Filter
			// mehrdeutig und den fremden, gruenen Test rot.
			const label = `${LABEL_FEHLSCHLAG}-9a`;
			await legePasskeyAn(page, label);
			await kuerzeZeremonieFrist(page, 4000);

			await context.clearCookies();
			await page.goto('/login');
			await page.fill('#username', process.env.GZ_E2E_USER ?? 'admin');

			// Erst JETZT das Geraet entfernen: login/begin antwortet 200, die
			// Zeremonie laeuft bis navigator.credentials.get() und scheitert dort
			// mangels Authentifikator -- der geraeteseitige Fehlschlag aus AC-9.
			await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId });
			authenticatorId = '';

			await page.getByTestId('login-passkey-btn').click();

			const fehler = page.getByTestId('login-passkey-error');
			await expect(fehler, 'nach dem Fehlschlag erscheint keine Fehlermeldung').toBeVisible({
				timeout: 15_000
			});
			const text = (await fehler.innerText()).trim();
			expect(text.length, `Fehlermeldung sagt nichts ("${text}")`).toBeGreaterThanOrEqual(15);
			expect(
				text,
				`Fehlermeldung ist technischer Rohtext ("${text}") statt Deutsch`
			).not.toMatch(/NotAllowedError|TypeError|undefined|invalid_credentials/);

			// Passwort-Weg bleibt sofort bedienbar.
			await expect(page.locator('button[type="submit"]')).toBeEnabled();
		});

		test('AC-9b: Zeitueberschreitung zeigt eine verstaendliche deutsche Fehlermeldung', async ({
			page,
			context
		}) => {
			test.setTimeout(45_000);
			const label = `${LABEL_FEHLSCHLAG}-9b`;
			await legePasskeyAn(page, label);

			await cdp.send('WebAuthn.setAutomaticPresenceSimulation', {
				authenticatorId,
				enabled: false
			});
			await kuerzeZeremonieFrist(page, 4000);

			await context.clearCookies();
			await page.goto('/login');
			await page.fill('#username', process.env.GZ_E2E_USER ?? 'admin');
			await page.getByTestId('login-passkey-btn').click();

			const fehler = page.getByTestId('login-passkey-error');
			await expect(fehler, 'nach der Zeitueberschreitung erscheint keine Fehlermeldung').toBeVisible(
				{ timeout: 20_000 }
			);
			const text = (await fehler.innerText()).trim();
			expect(text.length, `Fehlermeldung sagt nichts ("${text}")`).toBeGreaterThanOrEqual(15);
			expect(
				text,
				`Fehlermeldung ist technischer Rohtext ("${text}") statt Deutsch`
			).not.toMatch(/NotAllowedError|TypeError|undefined|invalid_credentials/);

			await expect(page.locator('button[type="submit"]')).toBeEnabled();
		});
	});
});
