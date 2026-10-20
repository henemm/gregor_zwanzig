// TDD RED — E2E (Live-Schicht), Issue #2278 (Epic #2345 P3): Durchklick-Test des einen Aktionsmodells.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — AC-2, AC-3, AC-4, AC-5, AC-8, AC-10, AC-12, AC-14, AC-16.
//
// "Jede angezeigte Aktion wirkt" (AC-16): fuer BEIDE Arten (Trip, Ortsvergleich) x BEIDE Viewports
// (Desktop, Mobil) wird jede Aktion aus Liste und Hub ausgeloest und die Wirkung gemessen — Request,
// Navigation oder Dialog. Der Versand wird per page.route abgefangen (Kunstantwort 200, es geht nichts an
// Empfaenger); es wird AUFGEZEICHNET, was ankommt.
//
// Verdrahtungsvertrag (hier festgelegt, /50 baut danach; bestehende IDs bleiben):
//   Desktop-Liste      : `trip-row-{id}` / `compare-tile-{id}` + `trip-row-menu-btn` / `compare-row-kebab`;
//                        Eintraege role=menuitem mit Label aus subscriptionActions
//   Mobil-Liste        : Karte `subscription-card-{id}`, Menue-Knopf `subscription-card-menu-{id}`,
//                        Blatt-Eintraege `subscription-action-{actionId}`; Filter-Pillen `status-filter-pill-{value}`
//   Hub                : Lebenszyklus-Knopf `subscription-kebab` (aria-label "Weitere Aktionen") in BEIDEN Viewports;
//                        Desktop: Dropdown, Eintraege role=menuitem; Mobil: oeffnet das SubscriptionActionSheet
//                        (surface='hub'), Eintraege `subscription-action-{actionId}`; Primaerknopf `subscription-hub-send`; Loesch-Dialog
//                        `{trip|compare}-detail-delete-confirm-{dialog,cancel,yes}`
//   Sende-Dialog       : `send-confirm-dialog`, `send-confirm-yes`, `send-confirm-cancel`; nur Trip:
//                        `send-confirm-berichtsart-morning` / `-evening` (Morgen vorausgewaehlt)
//
// RED heute: weder Aktionsquelle noch geteilte Bausteine existieren; Hub-Trip loescht nicht, mobiles
// Trip-"Senden" oeffnet nur die Vorschau, Compare-Hub sendet ohne Rueckfrage.
//
// Ausfuehren (aus frontend/, lokaler E2E-Stack, siehe e2e/ci-stack.sh):
//   npx playwright test e2e/aktionsmodell-durchklick.spec.ts
// Dieser Spec steht NICHT in ci_e2e_specs.txt; er laeuft in /50-implement und in /e2e-verify.
// AC-10 (zwei Nutzer) braucht GZ_ENV=staging im Ziel-Stack (registriereBestaetigtenZweitnutzer).

import { test, expect, type Page } from '@playwright/test';
import {
	login,
	createTestTrip,
	createTestComparePreset,
	createTestLocation,
	cleanupTracked,
	registriereBestaetigtenZweitnutzer
} from './helpers.js';

type Kind = 'trip' | 'vergleich';
const VIEWPORTS = {
	desktop: { width: 1280, height: 900 },
	mobil: { width: 390, height: 844 }
} as const;

const HEUTE = new Date().toISOString().slice(0, 10);

interface Objekt {
	id: string;
	name: string;
	/** Hub-Pfad */
	pfad: string;
}

async function legeAn(page: Page, kind: Kind): Promise<Objekt> {
	if (kind === 'trip') {
		const id = `e2e-gz-trip-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
		const t = await createTestTrip(page.request, {
			id,
			stages: [
				{
					id: `${id}-s1`,
					name: 'Etappe 1',
					date: HEUTE,
					waypoints: [{ id: `${id}-w1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			]
		});
		return { id: t.id, name: t.name, pfad: `/trips/${t.id}` };
	}
	const ort = await createTestLocation(page.request, { name: 'Durchklick-Ort', lat: 42.1, lon: 9.0 });
	const p = await createTestComparePreset(page.request, { locationIds: [ort.id] });
	return { id: p.id, name: p.name, pfad: `/compare/${p.id}` };
}

interface Aufzeichnung {
	senden: string[];
	loeschen: string[];
}
/** Versand abfangen (Kunstantwort); DELETE nur mitschreiben, dann durchlassen. */
async function aufzeichnen(page: Page, kind: Kind): Promise<Aufzeichnung> {
	const rec: Aufzeichnung = { senden: [], loeschen: [] };
	const sendMuster = kind === 'trip' ? '**/api/briefings/*/send*' : '**/api/briefings/*/send*';
	await page.route(sendMuster, async (route) => {
		const u = new URL(route.request().url());
		rec.senden.push(`${route.request().method()} ${u.pathname}${u.search}`);
		await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' });
	});
	const delMuster = kind === 'trip' ? '**/api/trips/*' : '**/api/compare/presets/*';
	await page.route(delMuster, async (route) => {
		if (route.request().method() === 'DELETE') {
			rec.loeschen.push(new URL(route.request().url()).pathname);
		}
		await route.fallback();
	});
	return rec;
}

/** Oeffnet das Aktionsmenue der Liste (Desktop: Zeilenmenue, Mobil: Karte -> Blatt). */
async function listenMenueOeffnen(page: Page, kind: Kind, o: Objekt, viewport: keyof typeof VIEWPORTS) {
	await page.goto(kind === 'trip' ? '/trips' : '/compare');
	if (viewport === 'desktop') {
		const zeile = page.getByTestId(kind === 'trip' ? `trip-row-${o.id}` : `compare-tile-${o.id}`);
		await expect(zeile).toBeVisible();
		await zeile.getByTestId(kind === 'trip' ? 'trip-row-menu-btn' : 'compare-row-kebab').click();
	} else {
		await expect(page.getByTestId(`subscription-card-${o.id}`)).toBeVisible();
		await page.getByTestId(`subscription-card-menu-${o.id}`).click();
	}
}

/** Waehlt eine Aktion nach ID im geoeffneten Listenmenue. */
async function aktionWaehlen(page: Page, viewport: keyof typeof VIEWPORTS, id: string, label: string) {
	if (viewport === 'desktop') await page.getByRole('menuitem', { name: label, exact: true }).click();
	else await page.getByTestId(`subscription-action-${id}`).click();
}

/** Hub: Lebenszyklus-Knopf oeffnen. */
async function hubMenueOeffnen(page: Page) {
	await page.getByTestId('subscription-kebab').click();
}
/** Hub: Beschriftungen der angebotenen Lebenszyklus-Aktionen (Desktop: Menue, Mobil: Blatt). */
async function hubLabels(page: Page, viewport: keyof typeof VIEWPORTS): Promise<string[]> {
	const eintraege =
		viewport === 'desktop' ? page.getByRole('menuitem') : page.locator('[data-testid^="subscription-action-"]');
	return (await eintraege.allTextContents()).map((t) => t.trim());
}
async function hubAktionWaehlen(page: Page, viewport: keyof typeof VIEWPORTS, id: string, label: string) {
	if (viewport === 'desktop') await page.getByRole('menuitem', { name: label, exact: true }).click();
	else await page.getByTestId(`subscription-action-${id}`).click();
}

for (const kind of ['trip', 'vergleich'] as const) {
	for (const viewport of ['desktop', 'mobil'] as const) {
		test.describe(`Durchklick ${kind} / ${viewport}`, () => {
			test.use({ viewport: VIEWPORTS[viewport] });
			test.beforeEach(async ({ page }) => {
				await login(page);
			});
			test.afterEach(async ({ page }) => {
				await cleanupTracked(page.request);
			});

			test('Liste: Senden fragt nach, nennt das Ziel und sendet erst nach Bestaetigung (AC-3, AC-14)', async ({ page }) => {
				const o = await legeAn(page, kind);
				const rec = await aufzeichnen(page, kind);
				await listenMenueOeffnen(page, kind, o, viewport);
				await aktionWaehlen(page, viewport, 'send', 'Senden');

				const dialog = page.getByTestId('send-confirm-dialog');
				await expect(dialog).toBeVisible();
				await expect(dialog).toContainText(/Geht an|Im Konto|nicht bestätigt/);
				expect(rec.senden, 'vor der Bestaetigung darf nichts gesendet werden').toEqual([]);

				await page.getByTestId('send-confirm-cancel').click();
				expect(rec.senden).toEqual([]);

				await listenMenueOeffnen(page, kind, o, viewport);
				await aktionWaehlen(page, viewport, 'send', 'Senden');
				await page.getByTestId('send-confirm-yes').click();
				await expect.poll(() => rec.senden.length).toBe(1);
				expect(rec.senden[0]).toMatch(
					kind === 'trip' ? /^POST \/api\/briefings\/[^/]+\/send\?kind=route&report_type=morning$/ : /^POST \/api\/briefings\/[^/]+\/send\?kind=vergleich$/
				);
			});

			test('Liste: Alarme / Wetter-Metriken / Bearbeiten / Vorschau fuehren auf den Hub-Reiter (AC-8, AC-16)', async ({ page }) => {
				const o = await legeAn(page, kind);
				const ZIELE: Array<[string, string, string]> = [
					['alarms', 'Alarme', `${o.pfad}?tab=alarme`],
					['weather', 'Wetter-Metriken', `${o.pfad}?tab=wetter-metriken`],
					['preview', 'Vorschau', `${o.pfad}?tab=vorschau`]
				];
				for (const [id, label, ziel] of ZIELE) {
					await listenMenueOeffnen(page, kind, o, viewport);
					await aktionWaehlen(page, viewport, id, label);
					await expect(page).toHaveURL(new RegExp(ziel.replace(/[?]/g, '\\?')));
				}
				await listenMenueOeffnen(page, kind, o, viewport);
				await aktionWaehlen(page, viewport, 'edit', 'Bearbeiten');
				await expect(page).toHaveURL(new RegExp(o.pfad + '(\\?|$)'));
				// "Alert-Konfiguration" gibt es nirgends mehr
				await listenMenueOeffnen(page, kind, o, viewport);
				await expect(page.getByText('Alert-Konfiguration')).toHaveCount(0);
			});

			test('Liste: Pausieren und Fortsetzen wirken (Request, Status)', async ({ page }) => {
				const o = await legeAn(page, kind);
				await listenMenueOeffnen(page, kind, o, viewport);
				const schreib = page.waitForRequest((r) => ['PATCH', 'PUT'].includes(r.method()) && r.url().includes(o.id));
				await aktionWaehlen(page, viewport, 'pause', 'Pausieren');
				await schreib;
				await listenMenueOeffnen(page, kind, o, viewport);
				// jetzt steht dort "Fortsetzen"
				if (viewport === 'desktop') await expect(page.getByRole('menuitem').first()).toHaveText('Fortsetzen');
				else await expect(page.getByTestId('subscription-action-resume')).toBeVisible();
			});

			test('Liste: Loeschen fragt nach; Abbrechen loescht nicht, Bestaetigen loescht', async ({ page }) => {
				const o = await legeAn(page, kind);
				const rec = await aufzeichnen(page, kind);
				await listenMenueOeffnen(page, kind, o, viewport);
				await aktionWaehlen(page, viewport, 'delete', 'Löschen');
				const dialog = page.getByRole('dialog');
				await expect(dialog).toBeVisible();
				await dialog.getByRole('button', { name: 'Abbrechen' }).click();
				expect(rec.loeschen).toEqual([]);

				await listenMenueOeffnen(page, kind, o, viewport);
				await aktionWaehlen(page, viewport, 'delete', 'Löschen');
				await page.getByRole('dialog').getByRole('button', { name: 'Löschen' }).click();
				await expect.poll(() => rec.loeschen.length).toBe(1);
			});

			test('Hub: Lebenszyklus-Menue, Senden als Primaerknopf mit Sende-Dialog, Loeschen mit Namen (AC-3, AC-4, AC-5, AC-12)', async ({ page }) => {
				const o = await legeAn(page, kind);
				const rec = await aufzeichnen(page, kind);
				await page.goto(o.pfad);

				// Lebenszyklus-Menue: Pausieren/Fortsetzen · Archivieren/Reaktivieren · Loeschen
				await hubMenueOeffnen(page);
				await expect.poll(() => hubLabels(page, viewport)).toEqual(['Pausieren', 'Archivieren', 'Löschen']);
				await page.keyboard.press('Escape');
				if (viewport === 'mobil') await page.getByLabel('Schliessen').click().catch(() => {});

				// Primaerknopf Senden -> Dialog (kein Versand vor Bestaetigung)
				await page.getByTestId('subscription-hub-send').click();
				const dialog = page.getByTestId('send-confirm-dialog');
				await expect(dialog).toBeVisible();
				expect(rec.senden).toEqual([]);
				if (kind === 'trip') {
					// AC-4: Morgen/Abend, Vorauswahl Morgen; gesendet wird die gewaehlte Option
					await expect(page.getByTestId('send-confirm-berichtsart-morning')).toBeChecked();
					await page.getByTestId('send-confirm-berichtsart-evening').check();
				} else {
					await expect(page.getByTestId('send-confirm-berichtsart-morning')).toHaveCount(0);
				}
				await page.getByTestId('send-confirm-yes').click();
				await expect.poll(() => rec.senden.length).toBe(1);
				if (kind === 'trip') expect(rec.senden[0]).toContain('report_type=evening');
				else expect(rec.senden[0]).not.toContain('report_type');

				// Loeschen: Dialog mit Namen, erst Bestaetigen loest DELETE aus, danach Liste
				const praefix = kind === 'trip' ? 'trip' : 'compare';
				await hubMenueOeffnen(page);
				await hubAktionWaehlen(page, viewport, 'delete', 'Löschen');
				await expect(page.getByTestId(`${praefix}-detail-delete-confirm-dialog`)).toContainText(o.name);
				await page.getByTestId(`${praefix}-detail-delete-confirm-cancel`).click();
				expect(rec.loeschen).toEqual([]);
				await hubMenueOeffnen(page);
				await hubAktionWaehlen(page, viewport, 'delete', 'Löschen');
				await page.getByTestId(`${praefix}-detail-delete-confirm-yes`).click();
				await expect.poll(() => rec.loeschen.length).toBe(1);
				await expect(page).toHaveURL(kind === 'trip' ? /\/trips\/?$/ : /\/compare\/?$/);
			});
		});
	}
}

test.describe('AC-2: mobile Vergleichs-Liste hat Filter-Pillen (wie beim Trip)', () => {
	test.use({ viewport: VIEWPORTS.mobil });
	test('Alle · Aktiv · Geplant · Pausiert · Fertig', async ({ page }) => {
		await login(page);
		await page.goto('/compare');
		await expect(page.locator('[data-testid^="status-filter-pill-"]')).toHaveCount(5);
		await page.goto('/trips');
		await expect(page.locator('[data-testid^="status-filter-pill-"]')).toHaveCount(5);
	});
});

test.describe('AC-10: Sende-Dialog nennt nur das Ziel des angemeldeten Nutzers', () => {
	test('Nutzer B sieht in der Trip-Liste nur seine Adresse, nie die von A', async ({ page, browser }) => {
		await login(page);
		const username = `e2e-gz-b-${Date.now()}`;
		const kontext = await browser.newContext();
		const gast = kontext.request;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast, username, 'Test1234!x');
			// B legt seinen eigenen Trip an und oeffnet "Senden" im Hub
			const res = await gast.post('/api/trips', {
				data: {
					id: `e2e-gz-trip-${username}`,
					name: `E2E-GZ-Trip-${username}`,
					stages: [
						{
							id: 's1',
							name: 'E1',
							date: HEUTE,
							waypoints: [{ id: 'w1', name: 'S', lat: 42.1, lon: 9.0, elevation_m: 500 }]
						}
					]
				}
			});
			expect(res.ok()).toBeTruthy();
			const seite = await kontext.newPage();
			await seite.goto(`/trips/e2e-gz-trip-${username}`);
			await seite.getByTestId('subscription-hub-send').click();
			const dialog = seite.getByTestId('send-confirm-dialog');
			await expect(dialog).toContainText(`${username}@example.com`);
			const adminProfil = await (await page.request.get('/api/auth/profile')).json();
			if (adminProfil?.mail_to) await expect(dialog).not.toContainText(adminProfil.mail_to);
		} finally {
			await gast.delete(`/api/trips/e2e-gz-trip-${username}`).catch(() => {});
			await kontext.close();
		}
	});
});

// Adversary F001 (#2278): die Sperre muss am KNOPF wirken, nicht nur im Modell. Zustand "kein Kanal kann
// liefern" wird echt hergestellt: frischer, bestaetigter Zweitnutzer leert sein mail_to (email == mail_to
// => wirksame Adresse unveraendert, sofort geschrieben, auth.go "mail_to leeren"). Das Profil, das der
// Dialog sieht, hat dann KEIN mail_to => sendTargetLabel sperrt. page.route auf das Profil geht nicht:
// es wird serverseitig geladen (+page.server.ts -> loadProfile). Braucht GZ_ENV=staging wie AC-10.
test.describe('AC-3: Sende-Dialog sperrt Bestaetigen, wenn kein Kanal liefern kann', () => {
	test('Hub-Trip ohne mail_to: send-confirm-yes ist disabled, es geht nichts raus', async ({ page, browser }) => {
		await login(page);
		const username = `e2e-gz-c-${Date.now()}`;
		const kontext = await browser.newContext();
		const gast = kontext.request;
		const tripId = `e2e-gz-trip-${username}`;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast, username, 'Test1234!x');
			const leer = await gast.put('/api/auth/profile', { data: { mail_to: '' } });
			expect(leer.ok(), `mail_to leeren: ${leer.status()}`).toBeTruthy();
			const profil = await (await gast.get('/api/auth/profile')).json();
			expect(profil?.mail_to ?? '', 'Vorbedingung: Profil ohne mail_to').toBe('');

			const res = await gast.post('/api/trips', {
				data: {
					id: tripId,
					name: `E2E-GZ-Trip-${username}`,
					stages: [
						{
							id: 's1',
							name: 'E1',
							date: HEUTE,
							waypoints: [{ id: 'w1', name: 'S', lat: 42.1, lon: 9.0, elevation_m: 500 }]
						}
					]
				}
			});
			expect(res.ok()).toBeTruthy();
			const seite = await kontext.newPage();
			const gesendet: string[] = [];
			await seite.route('**/api/briefings/*/send*', async (route) => {
				gesendet.push(route.request().url());
				await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' });
			});
			await seite.goto(`/trips/${tripId}`);
			await seite.getByTestId('subscription-hub-send').click();
			await expect(seite.getByTestId('send-confirm-dialog')).toContainText('keine E-Mail-Adresse');
			await expect(seite.getByTestId('send-confirm-yes')).toBeDisabled();
			await seite.getByTestId('send-confirm-yes').click({ force: true }).catch(() => {});
			expect(gesendet, 'gesperrter Knopf darf nichts senden').toEqual([]);
		} finally {
			await gast.delete(`/api/trips/${tripId}`).catch(() => {});
			await kontext.close();
		}
	});
});
