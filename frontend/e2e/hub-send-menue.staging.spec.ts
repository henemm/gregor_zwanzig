// E2E (Staging) — Issue #3440 (S5a, Scheibe #2797, Epic #2791): Menü „Test schicken ▾“ in Trip- und Orte-Hub.
// Spec: docs/specs/modules/feat_3440_test_schicken_menue.md — AC-1, 2, 3, 4, 6, 10, 11, 12, 15, 17, 18, 20.
//
// Läuft NICHT im PR-CI, sondern in /e2e-verify bzw. /60-validate nach Push und Staging-Deploy:
//   cd frontend && npx playwright test --config playwright.3440-test-menue.staging.config.ts
// Umgebung (nie im Klartext ausgeben): GZ_AUTH_USER/GZ_AUTH_PASS = Prüfkonto (GZ_PRUEFKONTO_* aus der Staging-.env),
// ELEMENTLISTE_TRIP_ID / ELEMENTLISTE_ORTE_ID aus scripts/staging_pruefkonto_mockupdaten.py
// (Runbook docs/runbooks/staging_pruefkonto_seed.md), optional GZ_VALIDATOR_* (nginx).
//
// Echter Versand NUR für E-Mail und Telegram (Prüfkonto: bestätigte Adresse, verbundener Chat; Staging leitet Mail
// per force_test ins Stalwart-Test-Postfach). SMS und Premium-SMS werden nie real ausgelöst (Kosten seven.io):
// dort nur Zeilen-/Sperrdarstellung. Belegt wird hier, dass genau EIN Request mit `channel` abgeht und das Backend
// `sent_channels == [kanal]` meldet. Den Posteingang (Anzahl 1) prüft in /e2e-verify der Mail-Validator
// (`briefing_mail_validator.py --mail-type trip-briefing`) gegen das Stalwart-Test-Postfach.
//
// Zustand „Lücken“ (AC-4): nur lesende Konto-Abrufe werden im Browser umgeschrieben (elementliste_abgleich_logik.ts
// ersetzeKontoAntwort), das Konto selbst bleibt unverändert; Hub-Daten kommen dafür per Browser-Navigation.

import { test, expect, type Page, type Locator, type Request } from '@playwright/test';
import { KONTO_ABRUF, ersetzeKontoAntwort } from './elementliste_abgleich_logik.ts';
import { HUB_KINDS, HUB_SEL, createTestLocation, hubApiPath, seedHub, type HubKind } from './helpers';

test.describe.configure({ mode: 'serial' });

const KNOPF = 'subscription-hub-send';
const IDS: Record<HubKind, string> = {
	route: process.env.ELEMENTLISTE_TRIP_ID ?? '',
	vergleich: process.env.ELEMENTLISTE_ORTE_ID ?? ''
};
const HUB_PFAD = (kind: HubKind, id: string) => (kind === 'route' ? `/trips/${id}` : `/compare/${id}`);
const KANAL_NAMEN = ['E-Mail', 'Telegram', 'SMS', 'Premium-SMS'] as const;

interface Profil {
	mail_to?: string;
	email_verified?: boolean;
	telegram_chat_id?: string;
}
let profil: Profil = {};

test.beforeEach(async ({ page }) => {
	const user = process.env.GZ_AUTH_USER;
	const pass = process.env.GZ_AUTH_PASS;
	expect(user && pass, 'Vorbedingung: GZ_AUTH_USER/GZ_AUTH_PASS (Prüfkonto) gesetzt').toBeTruthy();
	const login = await page.request.post('/api/auth/login', { data: { username: user, password: pass } });
	expect(login.ok(), `Login HTTP ${login.status()}`).toBeTruthy();
	for (const kind of HUB_KINDS) expect(IDS[kind], `Vorbedingung: Seed-ID für ${kind} (ELEMENTLISTE_*_ID)`).not.toBe('');
	const res = await page.request.get('/api/auth/profile');
	expect(res.ok(), `GET /api/auth/profile HTTP ${res.status()}`).toBeTruthy();
	profil = (await res.json()) as Profil;
	expect(profil.mail_to && profil.email_verified === true, 'Vorbedingung: Prüfkonto mit bestätigter E-Mail').toBeTruthy();
	expect(profil.telegram_chat_id, 'Vorbedingung: Prüfkonto mit verbundenem Telegram').toBeTruthy();
});

test.afterEach(async ({ page }) => {
	await page.request.post('/api/auth/logout').catch(() => {});
});

// ── Werkzeuge ────────────────────────────────────────────────────────────────

async function oeffneHub(page: Page, kind: HubKind, id = IDS[kind]): Promise<void> {
	await page.goto(HUB_PFAD(kind, id), { waitUntil: 'domcontentloaded' });
	await expect(page.getByTestId(KNOPF)).toBeVisible({ timeout: 20_000 });
}

/** Hub per Browser-Navigation (Hub-Daten über __data.json), damit der Konto-Abruf umgeschrieben werden kann. */
async function oeffneHubImBrowser(page: Page, kind: HubKind): Promise<void> {
	await page.goto('/', { waitUntil: 'load' });
	const pfad = HUB_PFAD(kind, IDS[kind]);
	await page.evaluate((href) => {
		const a = document.createElement('a');
		a.href = href;
		a.id = 'e2e-gz-3440-nav';
		a.textContent = 'Hub';
		document.body.appendChild(a);
	}, pfad);
	await Promise.all([page.waitForURL((u) => u.pathname === pfad, { timeout: 20_000 }), page.click('#e2e-gz-3440-nav')]);
	await expect(page.getByTestId(KNOPF)).toBeVisible({ timeout: 20_000 });
}

function menue(page: Page): Locator {
	return page.locator('[data-abschnitt="test-menue"]');
}

async function oeffneMenue(page: Page): Promise<Locator> {
	const knopf = page.getByTestId(KNOPF);
	await expect(knopf).toHaveAttribute('aria-haspopup', 'menu');
	await expect(knopf).toHaveAttribute('aria-expanded', 'false');
	await knopf.click();
	await expect(menue(page)).toBeVisible();
	await expect(knopf).toHaveAttribute('aria-expanded', 'true');
	return menue(page);
}

const zeile = (m: Locator, name: string) => m.getByRole('menuitem').filter({ hasText: new RegExp(`^\\s*${name}(?![-\\w])`) });

/** Zählt Sende-Abrufe dieses Eintrags; `abbrechen` verhindert echten Versand. */
async function sendeAbrufe(page: Page, id: string, opts: { abbrechen: boolean }): Promise<Request[]> {
	const liste: Request[] = [];
	await page.route(`**/api/briefings/${encodeURIComponent(id)}/send**`, async (route) => {
		if (route.request().method() === 'POST') liste.push(route.request());
		if (opts.abbrechen) await route.abort();
		else await route.continue();
	});
	return liste;
}

async function bleibtOhneAbruf(liste: Request[]): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				if (liste.length) return liste.length;
				seit ||= Date.now();
				return Date.now() - seit >= 1_500 ? 'stabil' : 0;
			},
			{ timeout: 6_000, intervals: [200] }
		)
		.toBe('stabil');
}

const kanalAus = (r: Request) => new URL(r.url()).searchParams.get('channel');

// ── AC-1 / AC-17 / AC-2 ──────────────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-1/AC-17 (${kind}): Knopf öffnet das Menü am Knopf, kein Dialog „Briefing senden?“`, async ({ page }) => {
		await oeffneHub(page, kind);
		const m = await oeffneMenue(page);
		await expect(m).toHaveCount(1);
		await expect(page.getByTestId('send-confirm-dialog')).toHaveCount(0);
		await expect(page.getByText('Briefing senden?')).toHaveCount(0);
	});
}

test('AC-2 (Trip): Segment Morgen/Abend, Vorauswahl Morgen, Wechsel lässt das Menü offen', async ({ page }) => {
	await oeffneHub(page, 'route');
	const m = await oeffneMenue(page);
	const morgen = m.getByRole('radio', { name: 'Morgen-Briefing', exact: true });
	const abend = m.getByRole('radio', { name: 'Abend-Briefing', exact: true });
	await expect(morgen).toHaveAttribute('aria-checked', 'true');
	await abend.click();
	await expect(abend).toHaveAttribute('aria-checked', 'true');
	await expect(m).toBeVisible();
	await expect(page.getByTestId(KNOPF)).toHaveAttribute('aria-expanded', 'true');
});

test('AC-2 (Orte): kein Segment im Menü', async ({ page }) => {
	await oeffneHub(page, 'vergleich');
	const m = await oeffneMenue(page);
	await expect(m.getByRole('radio')).toHaveCount(0);
	await expect(m.getByText('Morgen-Briefing')).toHaveCount(0);
});

// ── AC-3 / AC-4 ──────────────────────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-3 (${kind}): vier Kanalzeilen in Reihenfolge, Ziele gekürzt, Telegram nur „verbunden“`, async ({ page }) => {
		await oeffneHub(page, kind);
		const m = await oeffneMenue(page);
		const texte = await m.getByRole('menuitem').allInnerTexts();
		const namen = texte.map((t) => KANAL_NAMEN.find((n) => t.trim().startsWith(n) && !t.trim().startsWith(`${n}-`)) ?? null).filter(Boolean);
		expect(namen).toEqual([...KANAL_NAMEN]);
		const lokal = (profil.mail_to ?? '').split('@')[0];
		await expect(zeile(m, 'E-Mail')).toContainText(`${lokal}@…`);
		await expect(zeile(m, 'E-Mail')).not.toContainText(profil.mail_to ?? '#');
		await expect(zeile(m, 'Telegram')).toContainText('verbunden');
		await expect(m).not.toContainText(profil.telegram_chat_id ?? '#');
		await expect(m).not.toContainText('Empfänger');
		await expect(m.getByRole('menuitem', { name: /Alle eingerichteten Kanäle/ })).toBeVisible();
		await expect(m).not.toContainText('Test-Alarm');
	});
}

for (const kind of HUB_KINDS) {
	test(`AC-4 (${kind}): Lücken — Telegram/SMS/Premium gesperrt mit Grund und Konto-Link, Klick sendet nichts`, async ({ page }) => {
		let umgeschrieben = 0;
		await page.route(KONTO_ABRUF, async (route) => {
			if (route.request().method() !== 'GET') return route.continue();
			const antwort = await route.fetch();
			const r = ersetzeKontoAntwort(route.request().url(), await antwort.text());
			if (r.geaendert) umgeschrieben++;
			await route.fulfill({ response: antwort, body: r.text });
		});
		const abrufe = await sendeAbrufe(page, IDS[kind], { abbrechen: true });
		await oeffneHubImBrowser(page, kind);
		expect(umgeschrieben, 'Zustand Lücken nicht hergestellt (kein Konto-Abruf umgeschrieben)').toBeGreaterThan(0);
		const m = await oeffneMenue(page);
		const faelle = [
			{ name: 'Telegram', grund: 'gesperrt: Telegram-Chat fehlt.', link: 'Im Konto verbinden →' },
			{ name: 'SMS', grund: 'gesperrt: Nummer noch nicht bestätigt.', link: 'Im Konto bestätigen →' },
			{ name: 'Premium-SMS', grund: 'gesperrt: Schick eine Nachricht vom Gerät', link: 'Im Konto prüfen →' }
		];
		for (const f of faelle) {
			const z = zeile(m, f.name);
			await expect(z).toHaveAttribute('aria-disabled', 'true');
			await expect(z).toContainText(f.grund);
			const link = z.getByRole('link', { name: f.link }).or(z.getByRole('button', { name: f.link }));
			await expect(link).toBeVisible();
			if (await z.getByRole('link', { name: f.link }).count()) {
				await expect(z.getByRole('link', { name: f.link })).toHaveAttribute('href', /\/account/);
			}
		}
		await zeile(m, 'Telegram').click({ force: true, position: { x: 8, y: 8 } });
		await bleibtOhneAbruf(abrufe);
	});
}

// ── AC-6 / AC-11: Einzelversand (echt, nur E-Mail und Telegram) ──────────────

for (const kind of HUB_KINDS) {
	for (const kanal of [
		{ name: 'E-Mail', id: 'email' },
		{ name: 'Telegram', id: 'telegram' }
	] as const) {
		test(`AC-6/AC-11 (${kind}, ${kanal.id}): genau ein Request mit channel, nur dieser Kanal bedient, Rückmeldung 5 s`, async ({ page }) => {
			const abrufe = await sendeAbrufe(page, IDS[kind], { abbrechen: false });
			await oeffneHub(page, kind);
			const m = await oeffneMenue(page);
			const antwortP = page.waitForResponse((r) => r.url().includes(`/api/briefings/${IDS[kind]}/send`) && r.request().method() === 'POST', { timeout: 150_000 });
			await zeile(m, kanal.name).click();
			await expect(page.getByTestId(KNOPF)).toHaveAttribute('aria-expanded', 'false');
			const antwort = await antwortP;
			expect(abrufe).toHaveLength(1);
			expect(kanalAus(abrufe[0])).toBe(kanal.id);
			expect(antwort.status(), await antwort.text()).toBe(200);
			expect(((await antwort.json()) as { sent_channels?: string[] }).sent_channels).toEqual([kanal.id]);
			const ok = page.getByTestId('test-schicken-ok');
			const briefing = kind === 'route' ? 'Morgen-Briefing' : 'Briefing';
			await expect(ok).toHaveText(new RegExp(`^${briefing} an ${kanal.name} geschickt · .+ · \\d{2}:\\d{2}$`));
			await expect(ok).toBeHidden({ timeout: 8_000 });
		});
	}
}

test('AC-11 (Orte, Handy 390 px): Rückmeldung sichtbar und gleich aufgebaut', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await oeffneHub(page, 'vergleich');
	const m = await oeffneMenue(page);
	await zeile(m, 'E-Mail').click();
	await expect(page.getByTestId('test-schicken-ok')).toBeVisible({ timeout: 150_000 });
	await expect(page.getByTestId('test-schicken-ok')).toHaveText(/^Briefing an E-Mail geschickt · .+ · \d{2}:\d{2}$/);
});

// ── AC-10: Alle eingerichteten Kanäle ────────────────────────────────────────

test('AC-10 (Trip): „Alle eingerichteten Kanäle“ sendet ohne channel, Rückmeldung je Kanal', async ({ page }) => {
	const abrufe = await sendeAbrufe(page, IDS.route, { abbrechen: false });
	await oeffneHub(page, 'route');
	const m = await oeffneMenue(page);
	const antwortP = page.waitForResponse((r) => r.url().includes(`/api/briefings/${IDS.route}/send`) && r.request().method() === 'POST', { timeout: 150_000 });
	await m.getByRole('menuitem', { name: /Alle eingerichteten Kanäle/ }).click();
	const antwort = await antwortP;
	expect(abrufe).toHaveLength(1);
	expect(kanalAus(abrufe[0])).toBeNull();
	const gesendet = ((await antwort.json()) as { sent_channels?: string[] }).sent_channels;
	expect(Array.isArray(gesendet), 'sent_channels fehlt in der Antwort').toBe(true);
	const ok = page.getByTestId('test-schicken-ok');
	await expect(ok).toContainText('Morgen-Briefing geschickt:');
	if (gesendet?.includes('email')) await expect(ok).toContainText('E-Mail ✓');
	for (const name of KANAL_NAMEN) await expect(ok).toContainText(name);
});

// ── AC-12: Fehler rot mit bestehendem Text ───────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-12 (${kind}): Fehlerantwort erscheint als test-schicken-fehler mit Server-Text`, async ({ page }) => {
		// Transportgrenze: die Fehlerform kommt wörtlich wie vom Backend (Vokabular send_outcomes, pytest prüft die Abbildung).
		await page.route(`**/api/briefings/${encodeURIComponent(IDS[kind])}/send**`, (route) =>
			route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'Kein Kanal erreichbar (E2E 3440).', code: 'channels_unreachable' }) })
		);
		await oeffneHub(page, kind);
		const m = await oeffneMenue(page);
		await zeile(m, 'Telegram').click();
		const fehler = page.getByTestId('test-schicken-fehler');
		await expect(fehler).toHaveText('Kein Kanal erreichbar (E2E 3440).');
		await expect(page.getByTestId('test-schicken-ok')).toHaveCount(0);
	});
}

// ── AC-15: Bedienung ─────────────────────────────────────────────────────────

test('AC-15 (Desktop): Escape und Außenklick schließen, Tastatur öffnet und bewegt den Fokus', async ({ page }) => {
	await sendeAbrufe(page, IDS.route, { abbrechen: true });
	await oeffneHub(page, 'route');
	const knopf = page.getByTestId(KNOPF);
	await oeffneMenue(page);
	await page.keyboard.press('Escape');
	await expect(menue(page)).toBeHidden();
	await expect(knopf).toHaveAttribute('aria-expanded', 'false');

	await oeffneMenue(page);
	await page.mouse.click(5, 880);
	await expect(menue(page)).toBeHidden();

	await knopf.focus();
	await page.keyboard.press('Enter');
	await expect(menue(page)).toBeVisible();
	await page.keyboard.press('ArrowDown');
	const fokus = await page.evaluate(() => document.activeElement?.closest('[data-abschnitt="test-menue"]') !== null);
	expect(fokus, 'Pfeiltaste bewegt den Fokus nicht ins Menü').toBe(true);
	await page.keyboard.press('Escape');
	await expect(knopf).toHaveAttribute('aria-expanded', 'false');
});

test('AC-15 (Handy 390 px): Sheet statt Dropdown, Zeilen mindestens 44 px hoch', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await oeffneHub(page, 'route');
	const m = await oeffneMenue(page);
	await expect(page.getByRole('dialog').filter({ has: m }).or(m.locator('xpath=ancestor::*[@role="dialog"]'))).toHaveCount(1);
	for (const z of await m.getByRole('menuitem').all()) {
		const box = await z.boundingBox();
		expect(box?.height ?? 0, `Zeile „${(await z.innerText()).split('\n')[0]}“ niedriger als 44 px`).toBeGreaterThanOrEqual(44);
	}
});

// ── AC-18: Listen behalten den Dialog ────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-18 (${kind}): Liste zeigt weiter den Dialog „Briefing senden?“, Versand erst nach Bestätigen`, async ({ page }) => {
		const abrufe = await sendeAbrufe(page, IDS[kind], { abbrechen: true });
		await page.goto(HUB_SEL[kind].liste.url);
		const z = page.getByTestId(HUB_SEL[kind].liste.zeile(IDS[kind]));
		await expect(z).toBeVisible({ timeout: 15_000 });
		await z.getByTestId(HUB_SEL[kind].liste.menue).click();
		await page.getByRole('menu').getByRole('menuitem', { name: 'Senden', exact: true }).click();
		const dialog = page.getByTestId('send-confirm-dialog');
		await expect(dialog).toBeVisible();
		await bleibtOhneAbruf(abrufe);
		await dialog.getByTestId('send-confirm-cancel').click();
		await expect(dialog).toBeHidden();
	});
}

// ── AC-20: archiviert gesperrt ───────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-20 (${kind}): archiviertes Abo — Knopf gesperrt, Menü öffnet sich nicht`, async ({ page }) => {
		// Vergleich braucht einen echten Ort (die CI-Seed-Orte gibt es auf Staging nicht, Muster hub-send-dialog-target).
		const ort = kind === 'vergleich' ? await createTestLocation(page.request, { name: `E2E-GZ-3440 Ort ${Date.now()}` }) : null;
		const hub = await seedHub(page.request, kind, ort ? { extra: { location_ids: [ort.id], schedule: 'manual' } } : {});
		try {
			const res = await page.request.patch(`${hubApiPath(kind, hub.id)}/state`, { data: { archived: true } });
			expect(res.ok(), `Archivieren HTTP ${res.status()}`).toBeTruthy();
			await oeffneHub(page, kind, hub.id);
			const knopf = page.getByTestId(KNOPF);
			await expect(knopf).toBeDisabled();
			await knopf.click({ force: true }).catch(() => {});
			await expect(menue(page)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
			if (ort) await page.request.delete(`/api/locations/${ort.id}`).catch(() => {});
		}
	});
}
