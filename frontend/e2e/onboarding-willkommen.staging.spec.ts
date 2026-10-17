// Live-E2E Onboarding S2 gegen Staging (Spec docs/specs/modules/onboarding_willkommen_checkliste.md).
//
//   AC-2  Bestandskonto (GZ_AUTH_USER, vor S2 angelegt) sieht weder Willkommen noch Checkliste,
//         ein frisch registrierter Wegwerf-Nutzer sieht beides.
//   AC-3  Neuer Nutzer ohne Trips/Vergleiche sieht den Willkommens-Hinweis.
//   AC-16 „+ Neuer Vergleich" (Kopfzeile, Willkommen) landet auf /compare/new.
//   AC-8  „Testmail senden" -> echte Mail im Postfach GENAU dieser Adresse
//         (IMAP, Stalwart-Test-Postfach) -> Checkliste zeigt „Testmail gesendet am <heute>".
//   AC-17 keine Konsolenfehler auf der Startseite (console error + pageerror).
//
// Testids (Vertrag mit den node:test-Dateien):
//   onboarding-willkommen, onboarding-testmail-senden, onboarding-willkommen-verstanden,
//   startklar-checkliste, startklar-punkt-<id>, startklar-testmail-senden, startklar-ausblenden
//
// Wegwerf-Nutzer: `gregor-test+<nutzer>@henemm.com` (Plus-Adresse, Muster
// kanal-an-aus-kette.staging.spec.ts). Staging erzwingt Stalwart (`force_test`),
// die Mail landet im Postfach `gregor-test`. Filter im geteilten Postfach: die
// eindeutige Plus-Adresse im To-Kopf (die Testmail traegt kein Betreff-Token).
// Registrierung und Login laufen ueber `context.request` des Browser-Kontexts,
// damit das Sitzungs-Cookie in der Seite landet.
//
// Ausfuehren (gegen Staging, aus frontend/; Zugangsdaten nie im Klartext):
//   set -a
//   source /home/hem/gregor_zwanzig/.claude/validator.env        # nginx-Basic-Auth
//   source /home/hem/gregor_zwanzig_staging/.env                 # GZ_AUTH_*, GZ_TEST_IMAP_*
//   set +a
//   npx playwright test --config=e2e/playwright.onboarding-willkommen.staging.config.ts \
//     e2e/onboarding-willkommen.staging.spec.ts
//
// Nicht in der CI-Ampel. Bekannte Grenze: Registrierung 5/Stunde je IP.
// „Erstes Briefing erhalten" ist hier NICHT gemessen (braucht planmaessigen Lauf,
// Spec: sonst NOT_MEASURABLE_ON_STAGING).

import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import {
	test,
	expect,
	type APIRequestContext,
	type Browser,
	type BrowserContext,
	type Page,
	request as apiRequest
} from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const NGINX_USER = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const NGINX_PASS = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
const APP_USER = process.env.GZ_AUTH_USER ?? process.env.E2E_USER ?? 'admin';
const APP_PASS = process.env.GZ_AUTH_PASS ?? process.env.E2E_PASS ?? 'test1234';
const GAST_PASSWORT = 'test1234';

// ---------------------------------------------------------------------------
// Helfer
// ---------------------------------------------------------------------------

async function neuerBrowserKontext(browser: Browser): Promise<BrowserContext> {
	return browser.newContext({
		baseURL: BASE,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: NGINX_USER, password: NGINX_PASS }
	});
}

/** Konsolenfehler und Seitenfehler einer Seite sammeln (AC-17). */
function konsolenFehler(page: Page): string[] {
	const fehler: string[] = [];
	page.on('console', (m) => {
		if (m.type() === 'error') fehler.push(`console: ${m.text()}`);
	});
	page.on('pageerror', (e) => fehler.push(`pageerror: ${e.message}`));
	return fehler;
}

/** Registrieren -> Staging-Token (Admin-Sitzung) -> bestaetigen -> anmelden, alles im Gast-Kontext. */
async function registriereWegwerfNutzer(
	admin: APIRequestContext,
	gast: APIRequestContext,
	username: string,
	email: string
): Promise<void> {
	const reg = await gast.post('/api/auth/register', { data: { username, password: GAST_PASSWORT, email } });
	if (![200, 201].includes(reg.status())) {
		throw new Error(`Registrierung fehlgeschlagen: HTTP ${reg.status()} ${await reg.text()}`);
	}
	const tokenAntwort = await admin.post('/api/auth/verify-email/staging-token', { data: { username } });
	if (!tokenAntwort.ok()) throw new Error(`Staging-Token-Testweg antwortet HTTP ${tokenAntwort.status()}`);
	const { token } = (await tokenAntwort.json()) as { token?: string };
	if (!token) throw new Error('Staging-Token-Testweg lieferte kein Token');
	const ok = await gast.post('/api/auth/verify-email', { data: { user: username, token } });
	if (!ok.ok()) throw new Error(`Bestaetigung fehlgeschlagen: HTTP ${ok.status()}`);
	const login = await gast.post('/api/auth/login', { data: { username, password: GAST_PASSWORT } });
	if (!login.ok()) throw new Error(`Login fehlgeschlagen: HTTP ${login.status()}`);
}

// IMAP per Python-stdlib (keine IMAP-Bibliothek im Frontend). Zugangsdaten NUR
// aus der Umgebung (GZ_TEST_IMAP_USER/_PASS = Test-Postfach gregor-test, NICHT
// die generischen GZ_IMAP_*), nichts davon wird ausgegeben.
const IMAP_SNIPPET = `
import email, imaplib, json, os, sys
from email.header import decode_header, make_header
adresse = sys.argv[1].lower()
imap = imaplib.IMAP4_SSL(
    os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
    int(os.environ.get("GZ_IMAP_PORT", "993")),
    timeout=20,
)
imap.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
imap.select("INBOX", readonly=True)
_, data = imap.search(None, "ALL")
treffer = []
ids = data[0].split()[-200:]
if ids:
    _, teile = imap.fetch(ids[0].decode() + ":" + ids[-1].decode(),
                          "(BODY.PEEK[HEADER.FIELDS (SUBJECT TO DATE)])")
    for teil in teile:
        if not isinstance(teil, tuple):
            continue
        msg = email.message_from_bytes(teil[1])
        to = str(make_header(decode_header(msg.get("To", ""))))
        if adresse in to.lower():
            treffer.append({
                "subject": str(make_header(decode_header(msg.get("Subject", "")))),
                "to": to,
            })
imap.logout()
print(json.dumps(treffer))
`;

function mailsAn(adresse: string): { subject: string; to: string }[] {
	for (const pflicht of ['GZ_TEST_IMAP_USER', 'GZ_TEST_IMAP_PASS']) {
		if (!process.env[pflicht]) {
			throw new Error(`${pflicht} fehlt in der Umgebung (Test-Postfach gregor-test, nicht GZ_IMAP_*)`);
		}
	}
	const out = execFileSync('python3', ['-c', IMAP_SNIPPET, adresse], {
		env: process.env,
		encoding: 'utf-8',
		timeout: 60_000
	});
	return JSON.parse(out.trim().split('\n').pop() ?? '[]');
}

const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

function heuteTTMMJJJJ(): string {
	return new Intl.DateTimeFormat('de-DE', {
		timeZone: 'Europe/Berlin',
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	}).format(new Date());
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe.serial('Onboarding S2: Willkommen, Startklar-Checkliste, echte Testmail (Staging)', () => {
	let admin: APIRequestContext;
	let gastKontext: BrowserContext | undefined;
	let adminKontext: BrowserContext | undefined;
	let username = '';
	let adresse = '';

	test.beforeAll(async ({ browser }) => {
		assertNotProdBaseURL(BASE);
		admin = await apiRequest.newContext({
			baseURL: BASE,
			ignoreHTTPSErrors: true,
			httpCredentials: { username: NGINX_USER, password: NGINX_PASS }
		});
		const adminLogin = await admin.post('/api/auth/login', { data: { username: APP_USER, password: APP_PASS } });
		expect(adminLogin.ok(), `Admin-Login HTTP ${adminLogin.status()}`).toBeTruthy();

		const suffix = randomBytes(4).toString('hex');
		username = `e2eonb${suffix}`;
		adresse = `gregor-test+${username}@henemm.com`;
		gastKontext = await neuerBrowserKontext(browser);
		await registriereWegwerfNutzer(admin, gastKontext.request, username, adresse);
	});

	test.afterAll(async () => {
		// #2160: Kontoloeschung verlangt Re-Auth (Passwort-Konto).
		if (gastKontext && username) {
			const geloescht = await gastKontext.request.post('/api/auth/account/delete', {
				data: { password: GAST_PASSWORT }
			});
			expect(geloescht.status(), `Konto-Aufraeumen HTTP ${geloescht.status()}`).toBe(200);
		}
		await gastKontext?.close().catch(() => {});
		await adminKontext?.close().catch(() => {});
		await admin?.dispose().catch(() => {});
	});

	test('AC-2/AC-3/AC-17: neuer Nutzer sieht Willkommen und Checkliste, ohne Konsolenfehler', async () => {
		const profil = await gastKontext!.request.get('/api/auth/profile');
		expect(profil.ok()).toBeTruthy();
		const p = (await profil.json()) as Record<string, unknown>;
		expect(p.onboarding_pending, 'neues Konto traegt onboarding_pending').toBe(true);
		expect(p.mail_to, 'mail_to des Wegwerf-Nutzers').toBe(adresse);

		const page = await gastKontext!.newPage();
		const fehler = konsolenFehler(page);
		await page.goto('/');
		await expect(page.getByTestId('onboarding-willkommen')).toBeVisible();
		await expect(page.getByTestId('startklar-checkliste')).toBeVisible();
		await expect(page.getByTestId('startklar-punkt-email')).toHaveAttribute('data-erledigt', 'true');
		await expect(page.getByTestId('startklar-punkt-trip-oder-vergleich')).toHaveAttribute('data-erledigt', 'false');
		await expect(page.getByTestId('startklar-punkt-erstes-briefing')).toHaveAttribute('data-erledigt', 'false');
		await expect(page.getByTestId('startklar-punkt-testmail')).toHaveAttribute('data-pflicht', 'false');
		await expect(page.getByTestId('startklar-punkt-telegram')).toHaveAttribute('data-pflicht', 'false');
		await page.waitForLoadState('networkidle');
		expect(fehler, `Konsolenfehler auf /: ${fehler.join(' | ')}`).toEqual([]);
		await page.close();
	});

	test('AC-16: "+ Neuer Vergleich" in Kopfzeile und Willkommen fuehrt auf /compare/new', async () => {
		const page = await gastKontext!.newPage();
		await page.goto('/');
		await page.locator('header[data-slot="page-header"]').getByRole('link', { name: /Neuer Vergleich/ }).click();
		await expect(page).toHaveURL(/\/compare\/new(\?|$)/);

		await page.goto('/');
		const w = page.getByTestId('onboarding-willkommen');
		await expect(w).toBeVisible();
		await w.locator('a[href="/compare/new"]').first().click();
		await expect(page).toHaveURL(/\/compare\/new(\?|$)/);
		await page.close();
	});

	test('AC-8: "Testmail senden" -> echte Mail an genau diese Adresse -> Checkliste zeigt das Datum', async () => {
		const vorher = mailsAn(adresse).length;
		const page = await gastKontext!.newPage();
		const fehler = konsolenFehler(page);
		await page.goto('/');
		const antwort = page.waitForResponse(
			(r) => r.url().includes('/api/notify/test') && r.request().method() === 'POST'
		);
		await page.getByTestId('startklar-testmail-senden').click();
		const r = await antwort;
		const json = (await r.json()) as { status?: string; error?: string };
		expect(json.error, `Testmail-Fehler: ${json.error}`).toBeUndefined();
		expect(json.status).toBe('ok');

		let mails: { subject: string; to: string }[] = [];
		for (let i = 0; i < 18; i++) {
			mails = mailsAn(adresse);
			if (mails.length > vorher) break;
			await pause(10_000);
		}
		expect(mails.length, `keine Testmail an ${adresse} im Test-Postfach (vorher ${vorher})`).toBeGreaterThan(vorher);
		for (const m of mails) expect(m.to.toLowerCase()).toContain(adresse.toLowerCase());

		await page.reload();
		const punkt = page.getByTestId('startklar-punkt-testmail');
		await expect(punkt).toContainText(heuteTTMMJJJJ());
		await expect(page.getByTestId('startklar-testmail-senden')).toHaveCount(0);
		expect(fehler, `Konsolenfehler: ${fehler.join(' | ')}`).toEqual([]);
		await page.close();
	});

	// ---- Klick-Verdrahtung (Fix-Loop 2, F005) --------------------------------
	// Die Knoepfe werden hier geklickt und an der WIRKUNG gemessen (PUT/POST an die
	// API, Profil-Flags serverseitig, Zustand nach Neuladen) -- nicht an
	// Quelltext. Reihenfolge ist Teil des Vertrags: das Willkommen-Testmail-Knopf
	// steht nur, solange "Verstanden" nicht gedrueckt ist; der Checklisten-Knopf
	// (AC-8 oben) nur, solange noch keine Testmail ging.

	async function dismissFlags(): Promise<{ onboarding: boolean; checkliste: boolean }> {
		const r = await gastKontext!.request.get('/api/auth/profile');
		expect(r.ok()).toBeTruthy();
		const p = (await r.json()) as Record<string, unknown>;
		return { onboarding: p.onboarding_dismissed === true, checkliste: p.checklist_dismissed === true };
	}

	test('Verdrahtung: Willkommen-Knopf "Testmail senden" loest die Testmail aus (POST /api/notify/test, email)', async () => {
		const page = await gastKontext!.newPage();
		await page.goto('/');
		await expect(page.getByTestId('onboarding-willkommen')).toBeVisible();
		const anfrage = page.waitForRequest(
			(r) => r.url().includes('/api/notify/test') && r.method() === 'POST'
		);
		const antwort = page.waitForResponse(
			(r) => r.url().includes('/api/notify/test') && r.request().method() === 'POST'
		);
		await page.getByTestId('onboarding-testmail-senden').click();
		expect((await anfrage).postDataJSON()).toEqual({ channel: 'email' });
		const json = (await (await antwort).json()) as { status?: string; error?: string };
		expect(json.error, `Testmail-Fehler: ${json.error}`).toBeUndefined();
		expect(json.status).toBe('ok');
		await page.close();
	});

	test('Verdrahtung: "Verstanden" setzt NUR onboarding_dismissed -- Willkommen weg, Checkliste bleibt', async () => {
		expect(await dismissFlags(), 'Ausgangslage').toEqual({ onboarding: false, checkliste: false });
		const page = await gastKontext!.newPage();
		await page.goto('/');
		await expect(page.getByTestId('onboarding-willkommen')).toBeVisible();
		const put = page.waitForResponse(
			(r) => r.url().includes('/api/auth/profile') && r.request().method() === 'PUT'
		);
		await page.getByTestId('onboarding-willkommen-verstanden').click();
		expect((await put).ok()).toBeTruthy();

		await page.reload();
		await expect(page.getByTestId('onboarding-willkommen')).toHaveCount(0);
		await expect(page.getByTestId('startklar-checkliste')).toBeVisible();
		expect(await dismissFlags(), 'nur onboarding_dismissed darf true sein').toEqual({
			onboarding: true,
			checkliste: false
		});
		await page.close();
	});

	test('Verdrahtung: "Ausblenden" setzt NUR checklist_dismissed -- Checkliste weg nach Neuladen', async () => {
		const page = await gastKontext!.newPage();
		await page.goto('/');
		await expect(page.getByTestId('startklar-checkliste')).toBeVisible();
		const put = page.waitForResponse(
			(r) => r.url().includes('/api/auth/profile') && r.request().method() === 'PUT'
		);
		await page.getByTestId('startklar-ausblenden').click();
		expect((await put).ok()).toBeTruthy();

		await page.reload();
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
		await expect(page.getByTestId('startklar-checkliste')).toHaveCount(0);
		expect(await dismissFlags(), 'jetzt beide, "Ausblenden" darf "Verstanden" nicht zuruecknehmen').toEqual({
			onboarding: true,
			checkliste: true
		});
		await page.close();
	});

	test('AC-2: Bestandskonto (GZ_AUTH_USER, vor S2 angelegt) sieht weder Willkommen noch Checkliste', async ({ browser }) => {
		adminKontext = await neuerBrowserKontext(browser);
		const login = await adminKontext.request.post('/api/auth/login', {
			data: { username: APP_USER, password: APP_PASS }
		});
		expect(login.ok(), `Admin-Login HTTP ${login.status()}`).toBeTruthy();
		const profil = (await (await adminKontext.request.get('/api/auth/profile')).json()) as Record<string, unknown>;
		expect(profil.onboarding_pending, 'Bestandskonto traegt das Merkmal nicht').toBe(false);

		const page = await adminKontext.newPage();
		const fehler = konsolenFehler(page);
		await page.goto('/');
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
		await expect(page.getByTestId('onboarding-willkommen')).toHaveCount(0);
		await expect(page.getByTestId('startklar-checkliste')).toHaveCount(0);
		await page.waitForLoadState('networkidle');
		expect(fehler, `Konsolenfehler auf / (Admin): ${fehler.join(' | ')}`).toEqual([]);
		await page.close();
	});
});
