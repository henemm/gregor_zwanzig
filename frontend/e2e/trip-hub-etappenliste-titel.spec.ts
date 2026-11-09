// E2E — Issue #2878: Etappenliste der Trip-Übersicht lesbar (D1), Hub-Titel mobil ungekürzt (D2).
//
// Spec: docs/specs/modules/fix_2878_etappenliste_und_titel.md — AC-1 … AC-5 (EL-1 … EL-5).
// Gemessen wird im echten Browser (boundingBox, getComputedStyle, scrollWidth), nicht am Quelltext:
//   - EL-1 (1280 px, de/en): jede Etappenzeile zeigt den Namen (> 80 px breit, nicht leer), das
//     Datum steht in EINER Zeile; die Meta-Teile (Datum, WP …) brechen auch in einem extrem
//     schmalen Behälter nie in sich um (Stresstest: Meta-Zeile kurz auf 1 px gesetzt, gemessen,
//     zurückgesetzt) — Zusicherung „bricht nur zwischen den Teilen um".
//   - EL-2 (1280/1440 px): keine Etappenzeile läuft über; Zusammenfassung sichtbar genau dann,
//     wenn der gemessene Behälter ≥ 640 px breit ist.
//   - EL-3 (390 px, de/en): Titel „Korsika Nordteil" mit Kürzel, Status und Tageszahl vollständig
//     sichtbar (kein Ellipsis, keine Überbreite, ganzer Name im Text).
//   - EL-4 (390 px): 60-Zeichen-Name bricht mehrzeilig um, kein waagerechtes Scrollen, Stift
//     direkt am Titelende, Tippfläche ≥ 44 × 44 px.
//   - EL-5 (390 px): Trip und Ortsvergleich mit gleich langem Namen — beide vollständig sichtbar,
//     gleiche Umbruch-Stile am h1 (white-space, overflow-wrap, text-overflow).
//
// Pflicht-Mutationen (Spec Implementation Details 4): (a) `truncate` wieder am h1 ⇒ EL-3/EL-4/EL-5
// rot; (b) Container-Query entfernen ⇒ EL-1/EL-2 rot (Name 0 px); (c) `white-space: nowrap` der
// Meta-Teile entfernen ⇒ EL-1 rot (Stresstest: Datum bricht an den Bindestrichen um).
//
// Name und Datum werden per Text gefunden (nicht per Klasse), damit der RED-Lauf auf dem alten
// Markup am eigentlichen Fehler scheitert (Name 0 px breit) und nicht an einem fehlenden Selektor.
// Sprache per PUT /api/auth/profile (Muster anlege-rahmen-paritaet.spec.ts), im finally zurück auf
// de; die Fälle einer Datei laufen im selben Worker nacheinander (kein fullyParallel), der
// Sprachwechsel trifft also keine Nachbarfälle.
// Kein fester Schlaf, kein networkidle. Anmeldung über storageState (global.setup.ts).

import { test, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { E2E_TEST_PREFIX, HUB_KOPF_SEL, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const BREIT = { width: 1440, height: 900 };
const MOBIL = { width: 390, height: 844 };
const SPRACHEN = ['de', 'en'] as const;

const TITEL_15 = 'Korsika Nordteil';
const TITEL_60 = 'Korsika Nordteil von Calenzana ueber Asco bis nach Vizzavona';
const KUERZEL = 'GR20N';

/** ISO-Datum heute + n Tage (Trip „geplant" ⇒ Status-Schild und „in n Tagen" in der Titelzeile). */
function inTagen(n: number): string {
	return new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
}

const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 9.0, elevation_m });

/** Drei Etappen, Namen 12 bis 30 Zeichen (AC-1). */
const ETAPPEN = [
	{ id: 's1', name: 'Calenzana nach Ortu Piobbu', date: inTagen(12), waypoints: [wp('a', 42.5, 275), wp('b', 42.47, 1520)] },
	{ id: 's2', name: 'Carrozzu Hut', date: inTagen(13), waypoints: [wp('c', 42.45, 1270), wp('d', 42.43, 1500), wp('e', 42.42, 1430)] },
	{ id: 's3', name: 'Asco nach Tighjettu Huette', date: inTagen(14), waypoints: [wp('f', 42.4, 1420), wp('g', 42.38, 1640)] }
];

async function sprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

function seedTrip(request: APIRequestContext, name: string): Promise<SeededHub> {
	return seedHub(request, 'route', { extra: { name, shortcode: KUERZEL, stages: ETAPPEN } });
}

async function box(loc: Locator, was: string) {
	const b = await loc.boundingBox();
	expect(b, `${was} hat keine Box (unsichtbar?)`).not.toBeNull();
	return b!;
}

/** Zeilenhöhe in px (bei `normal` aus der Schriftgröße geschätzt). */
async function zeilenhoehe(loc: Locator): Promise<number> {
	return loc.evaluate((el) => {
		const cs = getComputedStyle(el);
		return parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.25;
	});
}

const zeile = (page: Page, i: number) => page.getByTestId(`trip-stage-row-${i}`);
const behaelter = (page: Page) => page.locator('[data-testid="hub-overview"] > div').first();

/** Titel (h1) des Hubs: Trip per testid, Vergleich über die Rolle (HUB_KOPF_SEL). */
function titel(page: Page, kind: HubKind): Locator {
	if (kind === 'route') return page.getByTestId('trip-detail-h1');
	return page.getByRole(HUB_KOPF_SEL.titelRolle.role, { level: HUB_KOPF_SEL.titelRolle.level }).filter({ visible: true }).first();
}

/** Messwerte des Titels: Überbreite, Ellipsis, sichtbarer Text, Umbruch-Stile. */
async function titelMessung(h1: Locator) {
	return h1.evaluate((el) => {
		const cs = getComputedStyle(el);
		return {
			scrollWidth: el.scrollWidth,
			clientWidth: el.clientWidth,
			text: (el as HTMLElement).innerText,
			textOverflow: cs.textOverflow,
			whiteSpace: cs.whiteSpace,
			overflowWrap: cs.overflowWrap
		};
	});
}

async function titelVollstaendig(page: Page, kind: HubKind, name: string, was: string): Promise<void> {
	const h1 = titel(page, kind);
	await expect(h1, `${was}: Titel nicht sichtbar`).toBeVisible({ timeout: 15_000 });
	const m = await titelMessung(h1);
	expect(m.text, `${was}: sichtbarer Text enthält nicht den ganzen Namen`).toContain(name);
	expect(m.textOverflow, `${was}: Titel wird mit Auslassungszeichen gekürzt`).not.toBe('ellipsis');
	expect(m.scrollWidth, `${was}: Titel läuft über (scrollWidth ${m.scrollWidth} > clientWidth ${m.clientWidth})`).toBeLessThanOrEqual(m.clientWidth);
	const b = await box(h1, `${was}: Titel`);
	expect(b.x + b.width, `${was}: Titel ragt rechts aus dem Fenster`).toBeLessThanOrEqual(MOBIL.width + 0.5);
}

/**
 * Stresstest der Meta-Zeile: kurz auf 1 px Breite gesetzt, je Teil gemessen, ob er mehrzeilig wird,
 * danach der alte Inline-Stil zurück. Belegt „bricht nur zwischen den Teilen um, nie in einem Teil".
 */
async function metaTeileBeiEngstemBehaelter(row: Locator) {
	return row.evaluate((el) => {
		const meta = el.querySelector<HTMLElement>('.stage-meta');
		if (!meta) return { teile: 0, mehrzeilig: ['(keine .stage-meta)'] };
		const alt = meta.style.width;
		meta.style.width = '1px';
		const teile = Array.from(meta.querySelectorAll<HTMLElement>('.stage-meta-part'));
		const mehrzeilig = teile
			.filter((t) => {
				const cs = getComputedStyle(t);
				const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.25;
				return t.getBoundingClientRect().height > lh * 1.5;
			})
			.map((t) => t.textContent ?? '');
		meta.style.width = alt;
		return { teile: teile.length, mehrzeilig };
	});
}

// ─── EL-1 (AC-1): Etappenname sichtbar, Datum einzeilig — 1280 px, de/en ────────────────────────
test('EL-1 (1280 px, de/en): jede Etappenzeile zeigt den Namen, das Datum steht in einer Zeile', async ({ page }) => {
	const hub = await seedTrip(page.request, `${E2E_TEST_PREFIX}Etappenliste`);
	try {
		await page.setViewportSize(DESKTOP);
		for (const lang of SPRACHEN) {
			await sprache(page, lang);
			await openHub(page, 'route', hub.id);
			await expect(page.getByTestId('hub-overview')).toBeVisible({ timeout: 15_000 });
			for (const [i, etappe] of ETAPPEN.entries()) {
				const row = zeile(page, i);
				await expect(row, `${lang}: Etappenzeile ${i} fehlt`).toBeVisible();
				const name = row.getByText(etappe.name, { exact: true });
				const nb = await box(name, `${lang}: Name Etappe ${i}`);
				expect(nb.width, `${lang}: Name „${etappe.name}" nur ${nb.width} px breit (unsichtbar)`).toBeGreaterThan(80);
				expect((await name.innerText()).trim(), `${lang}: Name Etappe ${i} leer`).not.toBe('');

				const datum = row.getByText(etappe.date);
				const db = await box(datum, `${lang}: Datum Etappe ${i}`);
				const lh = await zeilenhoehe(datum);
				expect(db.height, `${lang}: Datum ${etappe.date} bricht um (Höhe ${db.height} px, Zeile ${lh} px)`).toBeLessThanOrEqual(lh * 1.5);

				const stress = await metaTeileBeiEngstemBehaelter(row);
				expect(stress.teile, `${lang}: Meta-Zeile ohne eigene Teile (Datum, WP …)`).toBeGreaterThanOrEqual(2);
				expect(stress.mehrzeilig, `${lang}: Meta-Teile brechen in sich um`).toEqual([]);
			}
		}
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
		await hub.aufraeumen();
	}
});

// ─── EL-2 (AC-2): keine Überbreite, Zusammenfassung je nach gemessener Behälterbreite ──────────
test('EL-2 (1280/1440 px): keine Etappenzeile läuft über, Zusammenfassung sichtbar ab 640 px Behälter', async ({ page }) => {
	const hub = await seedTrip(page.request, `${E2E_TEST_PREFIX}Etappenliste-Breite`);
	try {
		for (const vp of [DESKTOP, BREIT]) {
			await page.setViewportSize(vp);
			await openHub(page, 'route', hub.id);
			await expect(zeile(page, 0)).toBeVisible({ timeout: 15_000 });
			const breite = (await box(behaelter(page), `${vp.width} px: Behälter der Etappenliste`)).width;
			for (let i = 0; i < ETAPPEN.length; i++) {
				const m = await zeile(page, i).evaluate((el) => {
					const s = el.querySelector<HTMLElement>('.stage-row-summary');
					return {
						scrollWidth: el.scrollWidth,
						clientWidth: el.clientWidth,
						summaryDisplay: s ? getComputedStyle(s).display : 'fehlt',
						summaryBreite: s ? s.getBoundingClientRect().width : 0
					};
				});
				expect(m.scrollWidth, `${vp.width} px: Zeile ${i} läuft über (${m.scrollWidth} > ${m.clientWidth})`).toBeLessThanOrEqual(m.clientWidth);
				const sichtbar = m.summaryDisplay !== 'none' && m.summaryDisplay !== 'fehlt' && m.summaryBreite > 0;
				expect(sichtbar, `${vp.width} px: Behälter ${breite} px — Zusammenfassung sichtbar=${sichtbar}`).toBe(breite >= 640);
			}
		}
	} finally {
		await hub.aufraeumen();
	}
});

// ─── EL-3 (AC-3): Titel „Korsika Nordteil" mobil vollständig, de/en ─────────────────────────────
test('EL-3 (390 px, de/en): Trip-Titel „Korsika Nordteil" vollständig sichtbar, kein Auslassungszeichen', async ({ page }) => {
	const hub = await seedTrip(page.request, TITEL_15);
	try {
		await page.setViewportSize(MOBIL);
		for (const lang of SPRACHEN) {
			await sprache(page, lang);
			await openHub(page, 'route', hub.id);
			await expect(page.getByTestId('trip-detail-status-badge').filter({ visible: true }).first(), `${lang}: Status-Schild fehlt (Vorbedingung)`).toBeVisible({ timeout: 15_000 });
			await titelVollstaendig(page, 'route', TITEL_15, `EL-3 (${lang})`);
		}
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
		await hub.aufraeumen();
	}
});

// ─── EL-4 (AC-4): 60-Zeichen-Name bricht um, Stift am Titelende ────────────────────────────────
test('EL-4 (390 px): 60-Zeichen-Name mehrzeilig, kein waagerechtes Scrollen, Stift am Titel mit 44×44 px', async ({ page }) => {
	expect(TITEL_60.length, 'Vorbedingung: Name hat 60 Zeichen').toBe(60);
	const hub = await seedTrip(page.request, TITEL_60);
	try {
		await page.setViewportSize(MOBIL);
		await openHub(page, 'route', hub.id);
		await titelVollstaendig(page, 'route', TITEL_60, 'EL-4');
		const h1 = titel(page, 'route');
		const hb = await box(h1, 'Titel');
		expect(hb.height, 'EL-4: Titel bricht nicht auf mehrere Zeilen um').toBeGreaterThan((await zeilenhoehe(h1)) * 1.5);

		const seite = await page.evaluate(() => document.documentElement.scrollWidth);
		expect(seite, 'EL-4: Seite läuft waagerecht über').toBeLessThanOrEqual(MOBIL.width);

		const stift = page.locator('[data-testid="trip-name-edit-toggle"]:visible');
		await expect(stift).toHaveCount(1);
		const sb = await box(stift, 'Stift');
		expect(sb.width, 'EL-4: Stift-Tippfläche zu schmal').toBeGreaterThanOrEqual(44);
		expect(sb.height, 'EL-4: Stift-Tippfläche zu niedrig').toBeGreaterThanOrEqual(44);
		expect(sb.x, 'EL-4: Stift links abgeschnitten').toBeGreaterThanOrEqual(0);
		expect(sb.x + sb.width, 'EL-4: Stift rechts abgeschnitten').toBeLessThanOrEqual(MOBIL.width + 0.5);
		const titelRechts = hb.x + hb.width;
		const titelUnten = hb.y + hb.height;
		const daneben = sb.x >= titelRechts - 1 && sb.x - titelRechts <= 16 && sb.y < titelUnten && sb.y + sb.height > hb.y;
		const darunter = sb.y >= titelUnten - 1 && sb.y - titelUnten <= 16;
		expect(daneben || darunter, `EL-4: Stift nicht direkt am Titel (Titel ${JSON.stringify(hb)}, Stift ${JSON.stringify(sb)})`).toBe(true);
	} finally {
		await hub.aufraeumen();
	}
});

// ─── EL-5 (AC-5): Trip und Ortsvergleich gleich — vollständig, gleiche Umbruch-Stile ───────────
test('EL-5 (390 px): Trip- und Vergleichs-Titel gleich langen Namens vollständig, gleiche Umbruch-Stile', async ({ page }) => {
	const trip = await seedTrip(page.request, TITEL_15);
	const vergleich = await seedHub(page.request, 'vergleich', { extra: { name: TITEL_15 } });
	try {
		await page.setViewportSize(MOBIL);
		const stile: Record<string, { whiteSpace: string; overflowWrap: string; textOverflow: string }> = {};
		for (const hub of [trip, vergleich]) {
			await openHub(page, hub.kind, hub.id);
			await titelVollstaendig(page, hub.kind, TITEL_15, `EL-5 (${hub.kind})`);
			const m = await titelMessung(titel(page, hub.kind));
			stile[hub.kind] = { whiteSpace: m.whiteSpace, overflowWrap: m.overflowWrap, textOverflow: m.textOverflow };
		}
		expect(stile.vergleich, 'EL-5: Umbruch-Stile Trip ≠ Vergleich').toEqual(stile.route);
	} finally {
		await trip.aufraeumen();
		await vergleich.aufraeumen();
	}
});
