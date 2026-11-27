// E2E (Staging) — Issue #3441 (S5b, Scheibe #2797): „Test-Alarm“ im Menü „Test schicken ▾“, Trip- und Orte-Hub.
// Spec: docs/specs/modules/feat_3441_test_alarm.md — AC-1, AC-2, AC-7, AC-8, AC-16, AC-17;
// Nachtrag #3463 (docs/specs/fast/fix-3463-test-alarm-kanaele.md): Mindestmenge der Kanäle, alle Fälle in DE und EN.
//
// Läuft NICHT im PR-CI, sondern in /e2e-verify nach Push und Staging-Deploy:
//   cd frontend && npx playwright test --config playwright.3441-test-alarm.staging.config.ts
// Umgebung (nie im Klartext ausgeben): Prüfkonto und Seed-IDs wählt e2e/pruefkontoZugang.ts (GZ_PRUEFKONTO_*
// vor GZ_AUTH_*; ELEMENTLISTE_TRIP_ID/ELEMENTLISTE_ORTE_ID optional, sonst Lookup des Seeds aus
// scripts/staging_pruefkonto_mockupdaten.py), optional GZ_VALIDATOR_* (nginx).
// Echter Versand an alle eingerichteten Alarm-Kanäle des Prüfkontos: mindestens E-Mail (bestätigte Adresse, Staging
// leitet ins Stalwart-Test-Postfach) und Telegram (verbundener Chat); SMS und Premium-SMS laufen auf Staging über
// Sandbox-Schlüssel (ohne Kosten) und dürfen zusätzlich in `sent_channels` stehen. Den Posteingang (Betreff mit
// [TEST], X-GZ-Mail-Type: deviation-alert, Anzahl 1 je Klick) prüft /e2e-verify im Stalwart-Test-Postfach.
// Sprache: je Block per PUT /api/auth/profile {language} umgestellt; afterAll setzt den Ausgangswert zurück.

import { test, expect, type Browser, type Page, type Locator, type Cookie, type Request } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import { pruefkontoZugang, seedIds } from './pruefkontoZugang.ts';

test.describe.configure({ mode: 'serial' });

type Sprache = 'de' | 'en';
// Wörtlich aus messages/{de,en}/test_schicken.json und zustellung.kanal.* (zustellung.json).
const TEXTE: Record<
	Sprache,
	{ alle: string; titel: string; untertitel: string; leer: string; geschickt: string; kanal: Record<string, string> }
> = {
	de: {
		alle: 'Alle eingerichteten Kanäle',
		titel: 'Test-Alarm',
		untertitel: 'Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle',
		leer: 'Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.',
		geschickt: 'Test-Alarm geschickt: ',
		kanal: { email: 'E-Mail', telegram: 'Telegram', sms: 'SMS', premium_sms: 'Premium-SMS' }
	},
	en: {
		alle: 'All set-up channels',
		titel: 'Test alert',
		untertitel: 'Sample alert with real values to all alert channels',
		leer: 'No alert channel set up, the test alert went nowhere.',
		geschickt: 'Test alert sent: ',
		kanal: { email: 'Email', telegram: 'Telegram', sms: 'SMS', premium_sms: 'Premium SMS' }
	}
};
const SPRACHEN: Sprache[] = ['de', 'en'];

const KNOPF = 'subscription-hub-send';
const IDS: Record<HubKind, string> = { route: '', vergleich: '' }; // befüllt in beforeAll (seedIds)
const HUB_PFAD = (kind: HubKind) => (kind === 'route' ? `/trips/${IDS[kind]}` : `/compare/${IDS[kind]}`);
let sitzung: Cookie[] = [];
let spracheVorher = '';

async function mitSitzung<T>(browser: Browser, f: (ctx: Awaited<ReturnType<Browser['newContext']>>) => Promise<T>): Promise<T> {
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	try {
		await ctx.addCookies(sitzung);
		return await f(ctx);
	} finally {
		await ctx.close();
	}
}

async function setzeSprache(browser: Browser, language: string): Promise<void> {
	await mitSitzung(browser, async (ctx) => {
		const r = await ctx.request.put('/api/auth/profile', { data: { language } });
		expect(r.ok(), `PUT /api/auth/profile language=${language}: HTTP ${r.status()}`).toBeTruthy();
	});
}

test.beforeAll(async ({ browser }) => {
	const { user, pass } = pruefkontoZugang();
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	const login = await ctx.request.post('/api/auth/login', { data: { username: user, password: pass } });
	expect(login.ok(), `Login HTTP ${login.status()}`).toBeTruthy();
	Object.assign(IDS, await seedIds(ctx.request));
	const profil = await ctx.request.get('/api/auth/profile');
	expect(profil.ok(), `GET /api/auth/profile HTTP ${profil.status()}`).toBeTruthy();
	spracheVorher = ((await profil.json()) as { language?: string }).language ?? 'de';
	sitzung = (await ctx.storageState()).cookies as Cookie[];
	await ctx.close();
});

test.beforeEach(async ({ page }) => {
	await page.context().addCookies(sitzung);
	for (const kind of HUB_KINDS) expect(IDS[kind], `Vorbedingung: Seed-ID für ${kind}`).not.toBe('');
});

test.afterAll(async ({ browser }) => {
	await mitSitzung(browser, async (ctx) => {
		// Ausgangssprache zuerst zurück und nachweisen (AC-4), Abmelden in jedem Fall.
		try {
			expect(spracheVorher, 'Vorbedingung: Ausgangssprache gemerkt').not.toBe('');
			const put = await ctx.request.put('/api/auth/profile', { data: { language: spracheVorher } });
			expect(put.ok(), `AC-4: PUT /api/auth/profile HTTP ${put.status()}`).toBeTruthy();
			const profil = await ctx.request.get('/api/auth/profile');
			expect(profil.ok(), `AC-4: GET /api/auth/profile HTTP ${profil.status()}`).toBeTruthy();
			const language = ((await profil.json()) as { language?: string }).language;
			expect(language, 'AC-4: Prüfkonto-Sprache zurück auf Ausgangswert').toBe(spracheVorher);
		} finally {
			await ctx.request.post('/api/auth/logout').catch(() => {});
		}
	});
});

async function oeffneMenue(page: Page, kind: HubKind): Promise<Locator> {
	await page.goto(HUB_PFAD(kind), { waitUntil: 'domcontentloaded' });
	await expect(page.getByTestId(KNOPF)).toBeVisible({ timeout: 20_000 });
	await page.getByTestId(KNOPF).click();
	const m = page.locator('[data-abschnitt="test-menue"]');
	await expect(m).toBeVisible();
	return m;
}

const eintrag = (m: Locator, sprache: Sprache) => m.getByRole('menuitem', { name: new RegExp(TEXTE[sprache].titel) });

async function alarmAbrufe(page: Page, kind: HubKind): Promise<Request[]> {
	const liste: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'POST' && r.url().includes(`/api/briefings/${IDS[kind]}/test-alert`)) liste.push(r);
	});
	return liste;
}

const KANAL_REIHENFOLGE = ['email', 'telegram', 'sms', 'premium_sms'];
const regexEscape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

for (const sprache of SPRACHEN) {
	const T = TEXTE[sprache];
	test.describe(`Sprache ${sprache.toUpperCase()}`, () => {
		test.beforeAll(async ({ browser }) => {
			await setzeSprache(browser, sprache);
		});

		for (const kind of HUB_KINDS) {
			for (const breite of [1280, 390]) {
				test(`AC-1 [${sprache}] (${kind}, ${breite} px): „${T.titel}“ mit Untertitel nach „${T.alle}“`, async ({ page }) => {
					await page.setViewportSize({ width: breite, height: 900 });
					const m = await oeffneMenue(page, kind);
					const texte = (await m.getByRole('menuitem').allInnerTexts()).map((t) => t.trim());
					const alle = texte.findIndex((t) => t.startsWith(T.alle));
					const alarm = texte.findIndex((t) => t.startsWith(T.titel));
					expect(alle, `Zeile „${T.alle}“ fehlt`).toBeGreaterThanOrEqual(0);
					expect(alarm, `${T.titel} muss nach „${T.alle}“ stehen`).toBe(alle + 1);
					await expect(eintrag(m, sprache)).toContainText(T.untertitel);
				});
			}
		}

		for (const kind of HUB_KINDS) {
			test(`AC-2/AC-8/AC-17 [${sprache}] (${kind}): echter Versand an mindestens E-Mail und Telegram, Doppelklick = ein Request, Rückmeldung 5 s`, async ({ page }) => {
				const abrufe = await alarmAbrufe(page, kind);
				const m = await oeffneMenue(page, kind);
				const antwortP = page.waitForResponse((r) => r.url().includes(`/api/briefings/${IDS[kind]}/test-alert`), { timeout: 150_000 });
				await eintrag(m, sprache).dblclick();
				const antwort = await antwortP;
				expect(antwort.status(), await antwort.text()).toBe(200);
				const gesendet = ((await antwort.json()) as { sent_channels?: string[] }).sent_channels ?? [];
				// Mindestmenge: E-Mail und Telegram müssen dabei sein, weitere eingerichtete Kanäle sind erlaubt.
				expect(gesendet).toEqual(expect.arrayContaining(['email', 'telegram']));
				const ok = page.getByTestId('test-schicken-ok');
				const beginn = `${T.kanal.email} ✓ · ${T.kanal.telegram} ✓`;
				await expect(ok).toHaveText(new RegExp(`^${regexEscape(T.geschickt + beginn)}.*· \\d{2}:\\d{2}$`));
				const text = (await ok.innerText()).trim();
				for (const k of KANAL_REIHENFOLGE.filter((k) => gesendet.includes(k))) {
					expect(text, `Rückmeldung nennt ${k}`).toContain(`${T.kanal[k]} ✓`);
				}
				expect(abrufe).toHaveLength(1);
				await expect(ok).toBeHidden({ timeout: 8_000 });
			});
		}

		for (const kind of HUB_KINDS) {
			test(`AC-7 [${sprache}] (${kind}): leere Kanalmenge zeigt den Leer-Text im Fehlerton`, async ({ page }) => {
				// Transportgrenze: die Fehlerform kommt wörtlich wie vom Backend (pytest prüft die Abbildung).
				await page.route(`**/api/briefings/${IDS[kind]}/test-alert**`, (route) =>
					route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'x', code: 'keine_alarm_kanaele' }) })
				);
				const m = await oeffneMenue(page, kind);
				await eintrag(m, sprache).click();
				await expect(page.getByTestId('test-schicken-fehler')).toHaveText(T.leer);
				await expect(page.getByTestId('test-schicken-ok')).toHaveCount(0);
			});
		}
	});
}
