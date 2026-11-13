// Abnahme — Issue #2913 Scheibe c2: Seitenkopf des Editor-Hubs nach Mockup (Trip + Orts-Vergleich).
// Spec: docs/specs/modules/feat_2913_c2_seitenkopf.md — AC-1 bis AC-6, AC-8 bis AC-11 (Browser-Anteil).
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html.
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste.
// Config (legt der Developer an, Phase 6 — Vorlage playwright.2913-metrikliste.staging.config.ts,
// Setup-Projekt fix-1895-modus-rueckbau.staging.setup.ts, testMatch /hub-kopf-c2-mockup\.staging\.spec\.ts/):
//   cd frontend && npx playwright test --config playwright.2913-c2-seitenkopf.staging.config.ts
//
// testids/Texte laut Vertrag im Kopf von
// src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts
// (hub-kopf-eyebrow, hub-kopf-meta, hub-kopf-aktivieren, subscription-hub-send „Test schicken ▾“).

import { test, expect, type Page, type Locator } from '@playwright/test';
import {
	hubApiPath,
	registriereBestaetigtenZweitnutzer,
	HUB_KINDS,
	HUB_SEL,
	HUB_KOPF_SEL,
	type HubKind,
	type SeededHub,
	seedHub,
	openHub,
	createTestLocation,
	cleanupTracked
} from './helpers';
import { wegwerfPasswort } from './stagingZugang';

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];
const VIEWPORTS = { desktop: { width: 1280, height: 900 }, mobil: { width: 390, height: 844 } } as const;

const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 2.7, elevation_m });
const ETAPPEN = [
	{ id: 'm1', name: 'Tag 1', date: '2027-02-23', waypoints: [wp('a', 39.58, 20), wp('b', 39.65, 420)] },
	{ id: 'm2', name: 'Tag 2', date: '2027-02-24', waypoints: [wp('c', 39.66, 380), wp('d', 39.67, 1100)] },
	{ id: 'm3', name: 'Tag 3', date: '2027-02-25', waypoints: [wp('e', 39.7, 900), wp('f', 39.71, 1350)] },
	{ id: 'm4', name: 'Tag 4', date: '2027-02-26', waypoints: [wp('g', 39.74, 400), wp('h', 39.75, 900)] }
];

const SOLL = {
	eltern: { route: { de: 'Trips', en: 'Trips' }, vergleich: { de: 'Orte', en: 'Locations' } },
	eyebrow: { route: { de: 'Trip · Mallorca', en: 'Trip · Mallorca' }, vergleich: { de: 'Orte · Münsterland', en: 'Locations · Münsterland' } },
	meta: {
		route: { de: /^.+ · 4 Etappen · \d+,\d km · ↑[\d.]+ m$/, en: /^.+ · 4 stages · \d+\.\d km · ↑[\d,]+ m$/ },
		vergleich: { de: /^3 Orte · Vergleichstabelle · Morgen-Briefing 07:00$/, en: /^3 locations · Comparison table · Morning briefing 07:00$/ }
	},
	knopf: { de: 'Test schicken ▾', en: 'Send test ▾' },
	kebab: { de: 'Weitere Aktionen', en: 'More actions' },
	vorlage: { de: { titel: 'Vorlage', gruppen: ['Vorlagen', 'Eigene'] }, en: { titel: 'Template', gruppen: ['Templates', 'Your own'] } }
} as const;
const ZAHL: Record<HubKind, string> = { route: '4', vergleich: '3' };

test.describe.configure({ mode: 'serial' });

let seeded: SeededHub[] = [];
let orte: string[] = [];

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

async function seed(page: Page, kind: HubKind, ueber: Record<string, unknown> = {}): Promise<string> {
	if (kind === 'route') {
		const hub = await seedHub(page.request, 'route', { extra: { region: 'Mallorca', activity: 'trekking', stages: ETAPPEN, ...ueber } });
		seeded.push(hub);
		return hub.id;
	}
	if (!ueber.location_ids) for (let i = 0; i < 3; i++) orte.push((await createTestLocation(page.request, { lat: 51.9 + i * 0.05, lon: 7.6 + i * 0.05 })).id);
	const hub = await seedHub(page.request, 'vergleich', {
		extra: {
			location_ids: ueber.location_ids ?? orte.slice(-3),
			morning_enabled: true,
			morning_time: '07:00:00',
			evening_enabled: false,
			display_config: { region: 'Münsterland' },
			...ueber
		}
	});
	seeded.push(hub);
	return hub.id;
}

const sichtbar = (page: Page | Locator, id: string): Locator => page.locator(`[data-testid="${id}"]:visible`).first();

test.afterEach(async ({ page }) => {
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
	for (const hub of seeded) await hub.aufraeumen();
	for (const o of orte) await page.request.delete(`/api/locations/${o}`).catch(() => {});
	seeded = [];
	orte = [];
	await cleanupTracked(page.request);
});

for (const kind of HUB_KINDS) {
	for (const lang of SPRACHEN) {
		for (const [vp, groesse] of Object.entries(VIEWPORTS) as Array<[keyof typeof VIEWPORTS, { width: number; height: number }]>) {
			test(`c2 Kopf ${kind} ${lang} ${vp}: Brotkrumen, Eyebrow, Pill, Meta, Knopf, Kebab, Reiter, Vorlage`, async ({ page }) => {
				await page.setViewportSize(groesse);
				await sprache(page, lang);
				const id = await seed(page, kind);
				await openHub(page, kind, id);

				// AC-1/AC-2: Leiste
				const leiste = sichtbar(page, HUB_KOPF_SEL.leiste);
				await expect(leiste).toBeVisible();
				const knopf = sichtbar(leiste, 'subscription-hub-send');
				await expect(knopf, 'AC-1: Knopf „Test schicken ▾“').toHaveText(SOLL.knopf[lang]);
				const kebab = sichtbar(leiste, 'subscription-kebab');
				await expect(kebab).toBeVisible();
				const kebabLabel = await kebab.evaluate((el) => el.getAttribute('aria-label') ?? el.querySelector('[aria-label]')?.getAttribute('aria-label') ?? '');
				expect(kebabLabel, 'Kebab „Weitere Aktionen“').toBe(SOLL.kebab[lang]);
				if (vp === 'desktop') {
					const krumen = sichtbar(page, HUB_KOPF_SEL.breadcrumb);
					const link = krumen.locator('a');
					await expect(link).toHaveCount(1);
					await expect(link).toHaveText(SOLL.eltern[kind][lang]);
					await expect(link).toHaveAttribute('href', kind === 'route' ? '/trips' : '/compare');
				}

				// AC-3/AC-4/AC-5: Kopf
				await expect(sichtbar(page, 'hub-kopf-eyebrow'), 'AC-3/AC-4: Eyebrow').toHaveText(SOLL.eyebrow[kind][lang]);
				await expect(sichtbar(page, 'hub-kopf-meta'), 'AC-3/AC-4: Meta-Zeile').toHaveText(SOLL.meta[kind][lang]);
				const status = sichtbar(page, HUB_KOPF_SEL.status);
				await expect(status.locator('[data-testid="trip-detail-status-badge"]'), 'AC-5: Status-Pill in der Titelzeile').toBeVisible();

				// AC-6: Reiterleiste mit Zähler und aria-current
				const reiter = page.locator(`[data-testid="${HUB_SEL[kind].reiter}-${HUB_SEL[kind].punkteReiter}"]:visible`).first();
				await expect(reiter.locator('[data-slot="segmented-badge"]'), 'AC-6: Zähler-Badge').toHaveText(ZAHL[kind]);
				const aktiv = page.locator('[role="tab"][data-state="active"]:visible').first();
				await expect(aktiv, 'AC-6: aktiver Reiter aria-current').toHaveAttribute('aria-current', 'page');
				await expect(page.locator('[role="tab"][data-state="inactive"][aria-current="page"]')).toHaveCount(0);

				// AC-11: kein horizontales Überlaufen
				const quer = await page.evaluate(() => {
					const el = document.scrollingElement ?? document.documentElement;
					const main = document.querySelector('main');
					return { seite: el.scrollWidth - el.clientWidth, main: main ? main.scrollWidth - main.clientWidth : 0 };
				});
				expect(quer.seite, 'AC-11: Seite scrollt quer').toBeLessThanOrEqual(0);
				expect(quer.main, 'AC-11: main scrollt quer').toBeLessThanOrEqual(0);
				await expect(knopf, 'AC-11: Knopf im Viewport').toBeInViewport();

				// AC-8: Vorlage-Karte im Reiter Wetter
				await openHub(page, kind, id, { tab: 'wetter' });
				const karte = page.locator('[data-abschnitt="vorlage"]:visible').first();
				await expect(karte).toBeVisible({ timeout: 15_000 });
				await expect(karte).toContainText(SOLL.vorlage[lang].titel);
				await sichtbar(karte, 'wetter-vorlage-picker').click();
				const gruppen = karte.locator('.wt-gruppe');
				await expect(gruppen).toHaveText([...SOLL.vorlage[lang].gruppen]);
				await expect(page.getByText(/ersetzt das Profil und steht im Kopf der Mail|replaces the profile/)).toHaveCount(0);
			});
		}
	}

	test(`c2 ${kind}: Brotkrumen-Elternteil führt zur Liste (Desktop, DE)`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		const id = await seed(page, kind);
		await openHub(page, kind, id);
		await sichtbar(page, HUB_KOPF_SEL.breadcrumb).locator('a').click();
		await expect(page).toHaveURL(kind === 'route' ? /\/trips\/?$/ : /\/compare\/?$/);
	});

	test(`c2 ${kind}: AC-9 Name inline ändern, nach Neuladen in Brotkrumen und Titel (Desktop, DE)`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		const id = await seed(page, kind);
		await openHub(page, kind, id);
		const p = HUB_SEL[kind].kopf;
		const stift = sichtbar(page, `${p}-name-edit-toggle`);
		await expect(stift).toBeVisible();
		await expect(stift, 'AC-9: Stift ohne sichtbaren Text').toHaveText('');
		expect((await stift.getAttribute('aria-label')) ?? '', 'AC-9: Stift mit aria-label').not.toBe('');
		const neu = `E2E-GZ-c2-${Date.now()}`;
		await stift.click();
		await sichtbar(page, `${p}-name-edit`).fill(neu);
		await sichtbar(page, `${p}-name-save`).click();
		await expect(page.locator('h1:visible').first()).toContainText(neu);
		await page.reload();
		await expect(page.locator('h1:visible').first(), 'AC-9: Name bleibt nach Neuladen').toContainText(neu);
		await expect(sichtbar(page, HUB_KOPF_SEL.breadcrumb)).toContainText(neu);
	});

	test(`c2 ${kind}: AC-9 Profil bleibt nach Name-Speichern und Neuladen unverändert (gespeichert + im Kopf gewählt)`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		const id = await seed(page, kind);
		const { kopf, profilFeld } = HUB_SEL[kind];
		const vorher = (await (await page.request.get(hubApiPath(kind, id))).json())[profilFeld];
		expect(vorher, 'AC-9: Seed trägt ein Profil').toBeTruthy();
		await openHub(page, kind, id);
		await sichtbar(page, `${kopf}-name-edit-toggle`).click();
		await sichtbar(page, `${kopf}-name-edit`).fill(`E2E-GZ-c2-profil-${Date.now()}`);
		await sichtbar(page, `${kopf}-name-save`).click();
		await expect(page.locator('h1:visible').first()).toContainText('E2E-GZ-c2-profil-');
		await page.reload();
		await expect(sichtbar(page, `${kopf}-profil-option-${vorher}`), 'AC-9: Profil nach Neuladen weiter gewählt').toHaveAttribute('data-selected', 'true');
		const nachher = (await (await page.request.get(hubApiPath(kind, id))).json())[profilFeld];
		expect(nachher, 'AC-9: gespeichertes Profil unverändert').toBe(vorher);
	});

	// AC-15: Profil-Zeile/-Chip bleibt im Ruhezustand sichtbar (Entfernung gehört zu #2796).
	for (const [vp, groesse] of Object.entries(VIEWPORTS) as Array<[keyof typeof VIEWPORTS, { width: number; height: number }]>) {
		test(`c2 ${kind} ${vp}: AC-15 Profil im Ruhezustand sichtbar`, async ({ page }) => {
			await page.setViewportSize(groesse);
			await sprache(page, 'de');
			const id = await seed(page, kind);
			const { kopf, profilFeld } = HUB_SEL[kind];
			const profil = (await (await page.request.get(hubApiPath(kind, id))).json())[profilFeld];
			await openHub(page, kind, id);
			if (vp === 'desktop') {
				const gewaehlt = sichtbar(page, `${kopf}-profil-option-${profil}`);
				await expect(gewaehlt, 'AC-15: Profil-Chip sichtbar').toBeVisible();
				await expect(gewaehlt).toHaveAttribute('data-selected', 'true');
			} else {
				const knopf = page.locator(`[data-testid="${kopf}-profil-knopf"]:visible`).first();
				await expect(knopf, 'AC-15: Profil-Knopf sichtbar (Handy)').toBeVisible();
				await expect(knopf).toHaveAttribute('data-selected-value', profil);
			}
		});
	}

	// AC-5 (Entwurf): Aktivieren neben der Pill, Klick führt zum Ziel, Pill wechselt nach Aktivierung durch Daten.
	test(`c2 ${kind}: AC-5 Entwurf bietet „Aktivieren“ an, Sprungziel stimmt, Pill wechselt auf aktiv`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		// Entwurf: Trip ohne datierte Etappen; Vergleich ohne Orte (deriveStatusFromPreset: location_ids leer).
		const id = await seed(page, kind, kind === 'route' ? { stages: [] } : { location_ids: [] });
		await openHub(page, kind, id);
		const pille = sichtbar(page, 'trip-detail-status-badge');
		await expect(pille, 'AC-5: Pill zeigt Entwurf').toHaveAttribute('data-status', 'draft');
		const aktivieren = sichtbar(sichtbar(page, HUB_KOPF_SEL.status), 'hub-kopf-aktivieren');
		await expect(aktivieren, 'AC-5: „Aktivieren“ neben der Pill').toBeVisible();
		await aktivieren.click();
		if (kind === 'route') await expect(page).toHaveURL(/[?&]tab=etappen/);
		else {
			await expect(page).toHaveURL(/[?&]tab=zustellung/);
			await expect(page).toHaveURL(/#versand/);
		}

		// Aktivieren durch Daten: Trip bekommt eine Etappe mit heutigem Datum (UTC wie deriveTripStatus) => aktiv;
		// Vergleich bekommt einen Ort (Zeitplan daily aus dem Seed) => aktiv. Eigener Wegwerf-Hub, PO-Daten unberührt.
		const pfad = hubApiPath(kind, id);
		const stand = await (await page.request.get(pfad)).json();
		let aenderung: Record<string, unknown>;
		if (kind === 'route') {
			const heute = new Date().toISOString().slice(0, 10);
			aenderung = { stages: [{ id: 'akt1', name: 'Heute', date: heute, waypoints: [wp('x', 39.58, 20), wp('y', 39.65, 420)] }] };
		} else {
			const ort = await createTestLocation(page.request, { lat: 51.9, lon: 7.6 });
			orte.push(ort.id);
			aenderung = { location_ids: [ort.id] };
		}
		const put = await page.request.put(pfad, { data: { ...stand, ...aenderung } });
		expect(put.ok(), `AC-5: Hub durch Daten aktivieren: HTTP ${put.status()}`).toBeTruthy();
		await openHub(page, kind, id);
		await expect(sichtbar(page, 'trip-detail-status-badge'), 'AC-5: Pill wechselt auf aktiv').toHaveAttribute('data-status', 'active');
		await expect(page.locator('[data-testid="hub-kopf-aktivieren"]')).toHaveCount(0);
	});

	// AC-7: Zähler folgt den Daten (eigener Wegwerf-Hub).
	test(`c2 ${kind}: AC-7 Zähler im Reiter folgt den Daten (N, dann N+1)`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		const id = await seed(page, kind);
		const reiterId = `${HUB_SEL[kind].reiter}-${HUB_SEL[kind].punkteReiter}`;
		const badge = () => page.locator(`[data-testid="${reiterId}"]:visible`).first().locator('[data-slot="segmented-badge"]');
		await openHub(page, kind, id);
		const n = Number(ZAHL[kind]);
		await expect(badge()).toHaveText(String(n));
		const pfad = hubApiPath(kind, id);
		const stand = await (await page.request.get(pfad)).json();
		let aenderung: Record<string, unknown>;
		if (kind === 'route') {
			aenderung = { stages: [...stand.stages, { id: 'm5', name: 'Tag 5', date: '2027-02-27', waypoints: [wp('i', 39.8, 300), wp('j', 39.81, 700)] }] };
		} else {
			const ort = await createTestLocation(page.request, { lat: 52.1, lon: 7.9 });
			orte.push(ort.id);
			aenderung = { location_ids: [...stand.location_ids, ort.id] };
		}
		const put = await page.request.put(pfad, { data: { ...stand, ...aenderung } });
		expect(put.ok(), `AC-7: PUT HTTP ${put.status()}`).toBeTruthy();
		await page.reload();
		await expect(badge(), 'AC-7: Zähler N+1').toHaveText(String(n + 1));
	});

	// AC-11 (langer Name): Wegwerf-Hub, Mobil.
	test(`c2 ${kind}: AC-11 Mobil mit sehr langem Namen ohne Quer-Scrollen`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.mobil);
		await sprache(page, 'de');
		const lang = `E2E-GZ-${'Langername-'.repeat(8)}Ende`;
		const id = await seed(page, kind, { name: lang });
		await openHub(page, kind, id);
		const quer = await page.evaluate(() => {
			const el = document.scrollingElement ?? document.documentElement;
			const main = document.querySelector('main');
			return { seite: el.scrollWidth - el.clientWidth, main: main ? main.scrollWidth - main.clientWidth : 0 };
		});
		expect(quer.seite, 'AC-11: Seite scrollt quer (langer Name)').toBeLessThanOrEqual(0);
		expect(quer.main, 'AC-11: main scrollt quer (langer Name)').toBeLessThanOrEqual(0);
		await expect(sichtbar(page, HUB_KOPF_SEL.leiste)).toBeVisible();
		await expect(sichtbar(sichtbar(page, HUB_KOPF_SEL.leiste), 'subscription-hub-send')).toBeInViewport();
		await expect(sichtbar(page, 'trip-detail-status-badge')).toBeVisible();
		await expect(page.locator(`[data-testid="${HUB_SEL[kind].reiter}-${HUB_SEL[kind].punkteReiter}"]:visible`).first().locator('[data-slot="segmented-badge"]')).toBeVisible();
	});
}

// AC-14: zwei Nutzer — jeder sieht im Hub nur Eigenes; fremde ID liefert keinen fremden Kopf.
// Zweitnutzer: frisch registriertes, bestätigtes Wegwerf-Konto (Staging-Testweg, wie s3a2794-teil3-zwei-nutzer-karten),
// am Ende samt Daten gelöscht. Es gibt kein festes zweites Staging-Konto, daher ohne test.skip lauffähig.
for (const kind of HUB_KINDS) {
	test(`c2 ${kind}: AC-14 zwei Nutzer sehen im Hub nur eigene Namen und Zähler`, async ({ page, browser }) => {
		test.setTimeout(180_000);
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		const idA = await seed(page, kind);
		const standA = await (await page.request.get(hubApiPath(kind, idA))).json();
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		const punkte = HUB_SEL[kind].punkteReiter;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2e2913c2${kind}${Date.now()}`, kennwort);
			// B: eigener Hub mit anderer Anzahl (2 statt 4 Etappen bzw. 1 statt 3 Orte)
			let hubB: SeededHub;
			let zahlB: string;
			if (kind === 'route') {
				hubB = await seedHub(gast.request, 'route', { extra: { region: 'Korsika', stages: ETAPPEN.slice(0, 2) } });
				zahlB = '2';
			} else {
				const ort = await createTestLocation(gast.request, { lat: 48.1, lon: 11.5 });
				hubB = await seedHub(gast.request, 'vergleich', { extra: { location_ids: [ort.id], morning_enabled: true, morning_time: '07:00:00', display_config: { region: 'Bayern' } } });
				zahlB = '1';
			}
			const standB = await (await gast.request.get(hubApiPath(kind, hubB.id))).json();
			const seiteB = await gast.newPage();
			await seiteB.setViewportSize(VIEWPORTS.desktop);
			const badge = (p: Page) => p.locator(`[data-testid="${HUB_SEL[kind].reiter}-${punkte}"]:visible`).first().locator('[data-slot="segmented-badge"]');

			await openHub(page, kind, idA);
			await openHub(seiteB, kind, hubB.id);
			await expect(sichtbar(page, HUB_KOPF_SEL.breadcrumb), 'A sieht eigenen Namen').toContainText(standA.name);
			await expect(sichtbar(seiteB, HUB_KOPF_SEL.breadcrumb), 'B sieht eigenen Namen').toContainText(standB.name);
			await expect(badge(page), 'A: eigener Zähler').toHaveText(ZAHL[kind]);
			await expect(badge(seiteB), 'B: eigener Zähler').toHaveText(zahlB);
			await expect(sichtbar(seiteB, HUB_KOPF_SEL.breadcrumb)).not.toContainText(standA.name);

			// B öffnet A's Hub: kein fremder Kopf, kein fremder Name
			await seiteB.goto(kind === 'route' ? `/trips/${idA}` : `/compare/${idA}`);
			await seiteB.waitForLoadState('networkidle').catch(() => {});
			expect(await seiteB.locator('body').innerText(), 'B sieht keinen fremden Namen').not.toContain(standA.name);
			await expect(seiteB.locator(`[data-testid="${HUB_KOPF_SEL.leiste}"]:visible`), 'B: kein fremder Kopf').toHaveCount(0);
			const lesen = await gast.request.get(hubApiPath(kind, idA));
			expect([403, 404], `B liest A's Objekt: HTTP ${lesen.status()}`).toContain(lesen.status());
			// A's Datenstand durch den Betrachtungsvorgang unverändert
			expect(await (await page.request.get(hubApiPath(kind, idA))).json(), 'A-Daten unverändert').toEqual(standA);
		} finally {
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
		}
	});
}
