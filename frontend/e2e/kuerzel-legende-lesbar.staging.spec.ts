// E2E (Staging) — Issue #1888 (Etappe E6, Scheibe B): die Kuerzel-Legende am
// Reihenfolge-Block ist auf dem Handy vollstaendig lesbar und ausreichend
// kontrastreich.
//
// Spec: docs/specs/modules/fix_1888_e6b_kuerzel_legende.md
//   AC-6  320-899 px: jede Legenden-Zeile vollstaendig lesbar, kein
//         display:none, keine Nullhoehe, kein horizontales Abschneiden — und
//         die SEITE scrollt nicht waagerecht (die Legende bricht innerhalb der
//         Karte um, statt das Layout zu schieben).
//   AC-7  Text-Hintergrund-Kontrast >= 4.5:1 (WCAG AA) fuer Kuerzel UND
//         Bedeutung; `--g-ink-4` ist als Farbe ausgeschlossen.
//
// WARUM BROWSER: Beides ist im Kern nicht belegbar. Praezedenzfall #1446 — eine
// Tabelle mit `display:none` meldet per DOM-Abfrage faelschlich „sichtbar".
// Deshalb wird hier GEOMETRISCH gemessen (`getBoundingClientRect`,
// `scrollWidth`/`clientWidth`, `innerText` gegen `textContent`) und der
// Kontrast aus den BERECHNETEN Style-Werten ausgerechnet, nicht behauptet.
//
// Die Kern-Schicht (AC-1..AC-5) steht in
// src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts und wird
// hier NICHT wiederholt.
//
// Ausfuehren (gegen Staging, aus frontend/, NACH Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.kuerzel-legende-lesbar.staging.config.ts

import {
	test,
	expect,
	type APIRequestContext,
	type Locator,
	type Page
} from '@playwright/test';
import { createTestLocation } from './helpers';

const TRIP_ID = 'e2e-1888-kuerzel-legende';

/** Anker der Legende — gleichlautend im AST-Waechter
 *  src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts. */
const LEGENDE = '[data-testid="metric-kuerzel-legend"]';

/** Handy-Breiten aus AC-6, beide Raender der Spanne eingeschlossen. 899 px ist
 *  der letzte Wert vor der Media-Query-Grenze (900 px). */
const BREITEN = [
	{ klasse: 'Kleinstes Handy', width: 320, height: 568 },
	{ klasse: 'Kleines Handy', width: 360, height: 640 },
	{ klasse: 'Kleines Handy', width: 375, height: 667 },
	{ klasse: 'Handy', width: 390, height: 844 },
	{ klasse: 'Handy', width: 414, height: 896 },
	{ klasse: 'Schmales Fenster', width: 600, height: 900 },
	{ klasse: 'Geteilter Bildschirm', width: 768, height: 1024 },
	{ klasse: 'Media-Query-Rand', width: 899, height: 900 }
] as const;

/** Bewusst die Groessen mit den LAENGSTEN Bedeutungen (bis 40 Zeichen, z.B.
 *  „Gefuehlte Tages-Tiefsttemperatur (Gehzeit)") — der Worst Case fuer den
 *  Umbruch gehoert in die Messung, nicht eine bequeme Auswahl. */
const TRIP_METRIKEN = [
	'wind_chill_day_low',
	'wind_chill_day_high',
	'wind_chill_night',
	'temperature_day_low',
	'temperature_day_high',
	'temperature_night',
	'thunder',
	'wind'
];

/** Vergleichs-Groessen mit doppeltem Kuerzel (`D`, `TF`) — dort traegt die
 *  Legende zusaetzlich die Auswertung und wird am laengsten. */
const VERGLEICH_METRIKEN = [
	'temp_max_c',
	'temp_min_c',
	'wind_chill_min_c',
	'wind_chill_max_c',
	'wind_max_kmh',
	'precip_sum_mm'
];

const aufgeraeumt: { presets: string[]; orte: string[] } = { presets: [], orte: [] };

// ═══════════════════════════════════════════════════════════════════════════
// Aufbau
// ═══════════════════════════════════════════════════════════════════════════

async function createTrip(request: APIRequestContext): Promise<void> {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E #1888 Kuerzel-Legende',
			display_config: {
				metrics: TRIP_METRIKEN.map((metric_id, order) => ({
					metric_id,
					enabled: true,
					bucket: 'primary',
					order
				}))
			},
			stages: [
				{
					id: `${TRIP_ID}-stage-1`,
					name: 'Etappe 1',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${TRIP_ID}-wp-1`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${TRIP_ID}-wp-2`, name: 'Ziel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
					]
				}
			]
		}
	});
	expect(res.ok(), `Trip-Anlage fehlgeschlagen: HTTP ${res.status()}`).toBeTruthy();
}

/** Einmal anlegen, in beiden Vergleichs-Tests wiederverwenden: die Orts-Ids
 *  leiten sich vom Namen ab, ein zweiter Aufruf liefe in HTTP 409. */
let vergleichId: string | null = null;

async function createVergleich(request: APIRequestContext): Promise<string> {
	if (vergleichId) return vergleichId;
	const ort1 = await createTestLocation(request, { name: '1888 Nord', lat: 46.5, lon: 8.1 });
	const ort2 = await createTestLocation(request, { name: '1888 Sued', lat: 46.9, lon: 8.4 });
	aufgeraeumt.orte.push(ort1.id, ort2.id);
	const res = await request.post('/api/compare/presets', {
		data: {
			name: 'E2E #1888 Kuerzel-Legende',
			location_ids: [ort1.id, ort2.id],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			display_config: { active_metrics: VERGLEICH_METRIKEN }
		}
	});
	expect(res.ok(), `Preset-Anlage HTTP ${res.status()}`).toBeTruthy();
	const id = (await res.json()).id as string;
	aufgeraeumt.presets.push(id);
	vergleichId = id;
	return id;
}

// Navigation. Beide Editoren werden in NORMALGROESSE geoeffnet und erst danach
// verkleinert — bei 320 px existiert der Reiter-Knopf teils gar nicht (gemessen
// in #1719 S4, dort derselbe Umweg).

async function oeffneTourenEditor(page: Page): Promise<Locator> {
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.goto(`/trips/${TRIP_ID}?tab=weather`);
	const reiter = page.getByTestId('trip-detail-tab-weather');
	await expect(reiter).toBeVisible({ timeout: 20_000 });
	await page.waitForLoadState('networkidle');
	await reiter.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 20_000 });
	await expect(tab.locator(LEGENDE).first()).toBeVisible({ timeout: 20_000 });
	return tab;
}

async function oeffneVergleichsEditor(page: Page, presetId: string): Promise<Locator> {
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.goto(`/compare/${presetId}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 20_000 });
	await page.waitForLoadState('networkidle');
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 20_000 });
	await expect(panel.locator(LEGENDE).first()).toBeVisible({ timeout: 20_000 });
	return panel;
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-6 — die Messung im echten Layout
// ═══════════════════════════════════════════════════════════════════════════

type ZeilenBefund = { text: string; verletzt: string[] };
type Messung = { zeilen: number; laengster: string; befunde: ZeilenBefund[] };

/** Misst jede Legenden-Zeile geometrisch. Laeuft IM BROWSER — nur dort kennen
 *  `getBoundingClientRect`, `scrollWidth` und `innerText` die tatsaechliche
 *  Darstellung. `toBeVisible()` allein genuegt nicht (#1446). */
async function messeLegende(legende: Locator): Promise<Messung> {
	await legende.scrollIntoViewIfNeeded();
	return legende.evaluate((wurzel) => {
		const befunde: { text: string; verletzt: string[] }[] = [];
		let laengster = '';
		const vw = window.innerWidth;

		const eigen = wurzel.getBoundingClientRect();
		const wurzelStil = getComputedStyle(wurzel);
		const wurzelFehler: string[] = [];
		if (wurzelStil.display === 'none') wurzelFehler.push('Legende hat display:none');
		if (wurzelStil.visibility === 'hidden') wurzelFehler.push('Legende hat visibility:hidden');
		if (eigen.width === 0 || eigen.height === 0) {
			wurzelFehler.push(`Legende ohne Ausdehnung (${Math.round(eigen.width)}x${Math.round(eigen.height)})`);
		}
		if (wurzelFehler.length > 0) befunde.push({ text: '(Legende selbst)', verletzt: wurzelFehler });

		const zeilen = Array.from(wurzel.querySelectorAll('li')) as HTMLElement[];
		if (zeilen.length === 0) {
			befunde.push({ text: '(keine Zeilen)', verletzt: ['Die Legende enthaelt keine <li>-Zeile'] });
			return { zeilen: 0, laengster: '', befunde };
		}

		for (const zeile of zeilen) {
			const r = zeile.getBoundingClientRect();
			const voll = (zeile.textContent ?? '').replace(/\s+/g, ' ').trim();
			const sichtbar = (zeile.innerText ?? '').replace(/\s+/g, ' ').trim();
			const verletzt: string[] = [];
			const stil = getComputedStyle(zeile);
			if (voll.length > laengster.length) laengster = voll;

			if (stil.display === 'none') verletzt.push('display:none');
			if (stil.visibility === 'hidden') verletzt.push('visibility:hidden');
			if (r.width === 0 || r.height === 0) {
				verletzt.push(`ohne Ausdehnung (${Math.round(r.width)}x${Math.round(r.height)})`);
			}
			// Waagerecht beschnitten? Das ist der Kern von AC-6.
			for (const [name, el] of [
				['Zeile', zeile],
				...Array.from(zeile.querySelectorAll('code, span')).map(
					(k, i) => [`Teil ${i + 1} <${k.tagName.toLowerCase()}>`, k as HTMLElement] as const
				)
			] as const) {
				const e = el as HTMLElement;
				if (e.scrollWidth > e.clientWidth + 1) {
					verletzt.push(
						`${name} beschnitten: scrollWidth ${e.scrollWidth} > clientWidth ${e.clientWidth}`
					);
				}
			}
			// Vollstaendig im Sichtfenster (waagerecht).
			if (r.left < -1 || r.right > vw + 1) {
				verletzt.push(
					`ausserhalb des Sichtfensters: x ${Math.round(r.left)}..${Math.round(r.right)}, ` +
						`Fensterbreite ${vw}`
				);
			}
			// Der gerenderte Text muss dem vollstaendigen Textinhalt entsprechen —
			// faengt ein `text-overflow: ellipsis`, das Zeichen still schluckt.
			if (sichtbar !== voll) {
				verletzt.push(`sichtbar ${JSON.stringify(sichtbar)} != vollstaendig ${JSON.stringify(voll)}`);
			}
			if (verletzt.length > 0) befunde.push({ text: voll, verletzt });
		}
		return { zeilen: zeilen.length, laengster, befunde };
	});
}

/** Waagerechte Seitenscroll-Leiste? Bei Ueberlauf werden die Verursacher
 *  mitgemeldet — sonst weiss niemand, ob die Legende schuld ist oder ein
 *  fremdes, vorbestehendes Bauteil. */
async function messeSeitenUeberlauf(
	page: Page
): Promise<{ scrollWidth: number; innerWidth: number; verursacher: string[] }> {
	return page.evaluate(() => {
		const de = document.documentElement;
		const verursacher: string[] = [];
		if (de.scrollWidth > window.innerWidth + 1) {
			for (const el of Array.from(document.querySelectorAll('*')) as HTMLElement[]) {
				const r = el.getBoundingClientRect();
				if (r.width === 0 || r.height === 0) continue;
				if (r.right <= window.innerWidth + 1) continue;
				const id = el.getAttribute('data-testid');
				verursacher.push(
					`<${el.tagName.toLowerCase()}${id ? ` data-testid="${id}"` : ''}` +
						`${el.className ? ` class="${String(el.className).slice(0, 60)}"` : ''}> ` +
						`rechts bei ${Math.round(r.right)}`
				);
				if (verursacher.length >= 6) break;
			}
		}
		return { scrollWidth: de.scrollWidth, innerWidth: window.innerWidth, verursacher };
	});
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-7 — Kontrast, gerechnet statt behauptet
// ═══════════════════════════════════════════════════════════════════════════

type Kontrastwert = {
	rolle: string;
	text: string;
	farbe: string;
	hintergrund: string;
	verhaeltnis: number;
	istInk4: boolean;
};

/** Holt Vorder- und Hintergrundfarbe je Legenden-Bestandteil und rechnet den
 *  WCAG-Kontrast aus. Der Hintergrund wird die Elternkette entlang aufgeloest —
 *  meldet das Element selbst `transparent`, misst man sonst gegen nichts. */
async function messeKontrast(legende: Locator): Promise<Kontrastwert[]> {
	return legende.evaluate((wurzel) => {
		function parse(farbe: string): [number, number, number, number] | null {
			const m = farbe.match(/rgba?\(([^)]+)\)/);
			if (!m) return null;
			const t = m[1].split(',').map((s) => parseFloat(s.trim()));
			return [t[0], t[1], t[2], t.length > 3 ? t[3] : 1];
		}
		function ueberlagern(
			vorn: [number, number, number, number],
			hinten: [number, number, number, number]
		): [number, number, number, number] {
			const a = vorn[3];
			return [
				vorn[0] * a + hinten[0] * (1 - a),
				vorn[1] * a + hinten[1] * (1 - a),
				vorn[2] * a + hinten[2] * (1 - a),
				1
			];
		}
		function leuchtdichte([r, g, b]: [number, number, number, number]): number {
			const k = [r, g, b].map((v) => {
				const s = v / 255;
				return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
			});
			return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
		}
		/** Erste nicht durchsichtige Hintergrundfarbe der Elternkette. */
		function hintergrundVon(el: HTMLElement): [number, number, number, number] {
			let n: HTMLElement | null = el;
			while (n) {
				const c = parse(getComputedStyle(n).backgroundColor);
				if (c && c[3] > 0) return [c[0], c[1], c[2], 1];
				n = n.parentElement;
			}
			return [255, 255, 255, 1]; // Seitenhintergrund als letzte Instanz
		}

		const ink4 = parse(
			getComputedStyle(document.documentElement).getPropertyValue('--g-ink-4').trim()
		);
		const werte: Kontrastwert[] = [];

		for (const zeile of Array.from(wurzel.querySelectorAll('li')) as HTMLElement[]) {
			const teile: [string, HTMLElement][] = [];
			const kuerzel = zeile.querySelector('code') as HTMLElement | null;
			const bedeutung = zeile.querySelector('span') as HTMLElement | null;
			if (kuerzel) teile.push(['Kuerzel', kuerzel]);
			// Die Auswertung („(Maximum)") steht im selben Textknoten wie der
			// Groessenname — sie traegt also dieselbe Farbe; gemessen wird sie
			// trotzdem eigens ausgewiesen, damit die Zahl im Bericht steht.
			if (bedeutung) {
				teile.push(['Bedeutung', bedeutung]);
				if (/\(.+\)/.test(bedeutung.textContent ?? '')) {
					teile.push(['Auswertung', bedeutung]);
				}
			}
			if (teile.length === 0) teile.push(['Zeile', zeile]);

			for (const [rolle, el] of teile) {
				const vorn = parse(getComputedStyle(el).color);
				if (!vorn) continue;
				const hinten = hintergrundVon(el);
				const effektiv = vorn[3] < 1 ? ueberlagern(vorn, hinten) : vorn;
				const l1 = leuchtdichte(effektiv);
				const l2 = leuchtdichte(hinten);
				const verhaeltnis =
					(Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
				werte.push({
					rolle,
					text: (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40),
					farbe: `rgb(${effektiv.slice(0, 3).map(Math.round).join(', ')})`,
					hintergrund: `rgb(${hinten.slice(0, 3).map(Math.round).join(', ')})`,
					verhaeltnis: Math.round(verhaeltnis * 100) / 100,
					istInk4: !!ink4 && Math.abs(vorn[0] - ink4[0]) < 2
						&& Math.abs(vorn[1] - ink4[1]) < 2 && Math.abs(vorn[2] - ink4[2]) < 2
				});
			}
		}
		return werte;
	});
}

/** Bericht der gemessenen Kontraste — echte Zahlen, auch im Erfolgsfall. */
function berichteKontrast(wo: string, werte: Kontrastwert[]): void {
	const gesehen = new Map<string, Kontrastwert>();
	for (const w of werte) gesehen.set(`${w.rolle}|${w.farbe}|${w.hintergrund}`, w);
	for (const w of gesehen.values()) {
		console.log(
			`  [Kontrast] ${wo} · ${w.rolle}: ${w.verhaeltnis}:1 ` +
				`(${w.farbe} auf ${w.hintergrund})${w.istInk4 ? '  ← --g-ink-4!' : ''}`
		);
	}
}

// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Issue #1888: die Kuerzel-Legende ist auf dem Handy lesbar', () => {
	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		for (const id of aufgeraeumt.presets) {
			await request.delete(`/api/compare/presets/${id}`).catch(() => {});
		}
		for (const id of aufgeraeumt.orte) {
			await request.delete(`/api/locations/${id}`).catch(() => {});
		}
	});

	test('AC-6: Trip-Editor — jede Legenden-Zeile bleibt in 320-899 px vollstaendig lesbar', async ({
		page,
		request
	}) => {
		await createTrip(request);
		const tab = await oeffneTourenEditor(page);
		const legende = tab.locator(LEGENDE).first();

		const befunde: string[] = [];
		for (const { klasse, width, height } of BREITEN) {
			await page.setViewportSize({ width, height });
			await page.waitForTimeout(250);

			await expect(
				legende,
				`AC-6 FAIL: die Legende ist bei ${width}px nicht sichtbar`
			).toBeVisible();

			const messung = await messeLegende(legende);
			expect(
				messung.zeilen,
				`AC-6: bei ${width}px enthaelt die Legende keine Zeile — dann misst dieser ` +
					`Test nichts und waere folgenlos gruen`
			).toBeGreaterThan(0);
			for (const b of messung.befunde) {
				for (const v of b.verletzt) {
					befunde.push(`${width}x${height} (${klasse}) · ${JSON.stringify(b.text)}: ${v}`);
				}
			}

			const ueberlauf = await messeSeitenUeberlauf(page);
			console.log(
				`  [AC-6] Trip ${width}x${height}: ${messung.zeilen} Zeilen gemessen, laengste ` +
					`${JSON.stringify(messung.laengster)} (${messung.laengster.length} Zeichen), ` +
					`Seite scrollWidth ${ueberlauf.scrollWidth} / innerWidth ${ueberlauf.innerWidth}`
			);
			if (ueberlauf.scrollWidth > ueberlauf.innerWidth + 1) {
				befunde.push(
					`${width}x${height} (${klasse}) · SEITE scrollt waagerecht: scrollWidth ` +
						`${ueberlauf.scrollWidth} > innerWidth ${ueberlauf.innerWidth}. ` +
						`Verursacher: ${ueberlauf.verursacher.join(' | ') || '(keiner ermittelbar)'}`
				);
			}
		}

		expect(
			befunde,
			`AC-6 FAIL (Trip-Editor): die Legende ist nicht in jeder Handy-Breite ` +
				`vollstaendig lesbar.\n  ${befunde.join('\n  ')}`
		).toEqual([]);
	});

	test('AC-6: Ortsvergleich-Editor — dieselbe Zusicherung', async ({ page, request }) => {
		const presetId = await createVergleich(request);
		const panel = await oeffneVergleichsEditor(page, presetId);
		const legende = panel.locator(LEGENDE).first();

		const befunde: string[] = [];
		for (const { klasse, width, height } of BREITEN) {
			await page.setViewportSize({ width, height });
			await page.waitForTimeout(250);

			await expect(
				legende,
				`AC-6 FAIL: die Vergleichs-Legende ist bei ${width}px nicht sichtbar`
			).toBeVisible();

			const messung = await messeLegende(legende);
			expect(
				messung.zeilen,
				`AC-6: bei ${width}px enthaelt die Vergleichs-Legende keine Zeile — dann ` +
					`misst dieser Test nichts und waere folgenlos gruen`
			).toBeGreaterThan(0);
			for (const b of messung.befunde) {
				for (const v of b.verletzt) {
					befunde.push(`${width}x${height} (${klasse}) · ${JSON.stringify(b.text)}: ${v}`);
				}
			}

			const ueberlauf = await messeSeitenUeberlauf(page);
			console.log(
				`  [AC-6] Vergleich ${width}x${height}: ${messung.zeilen} Zeilen gemessen, laengste ` +
					`${JSON.stringify(messung.laengster)} (${messung.laengster.length} Zeichen), ` +
					`Seite scrollWidth ${ueberlauf.scrollWidth} / innerWidth ${ueberlauf.innerWidth}`
			);
			if (ueberlauf.scrollWidth > ueberlauf.innerWidth + 1) {
				befunde.push(
					`${width}x${height} (${klasse}) · SEITE scrollt waagerecht: scrollWidth ` +
						`${ueberlauf.scrollWidth} > innerWidth ${ueberlauf.innerWidth}. ` +
						`Verursacher: ${ueberlauf.verursacher.join(' | ') || '(keiner ermittelbar)'}`
				);
			}
		}

		expect(
			befunde,
			`AC-6 FAIL (Ortsvergleich): die Legende ist nicht in jeder Handy-Breite ` +
				`vollstaendig lesbar.\n  ${befunde.join('\n  ')}`
		).toEqual([]);
	});

	test('AC-7: Trip-Editor — Kuerzel und Bedeutung halten WCAG AA (4.5:1)', async ({
		page,
		request
	}) => {
		await createTrip(request);
		const tab = await oeffneTourenEditor(page);
		const legende = tab.locator(LEGENDE).first();

		const zuSchwach: string[] = [];
		for (const { width, height } of [BREITEN[0], BREITEN[BREITEN.length - 1]]) {
			await page.setViewportSize({ width, height });
			await page.waitForTimeout(250);
			const werte = await messeKontrast(legende);
			expect(werte.length, `AC-7: keine messbaren Legenden-Bestandteile bei ${width}px`)
				.toBeGreaterThan(0);
			berichteKontrast(`Trip ${width}px`, werte);
			for (const w of werte) {
				if (w.verhaeltnis < 4.5) {
					zuSchwach.push(
						`${width}px · ${w.rolle} ${JSON.stringify(w.text)}: ${w.verhaeltnis}:1 ` +
							`(${w.farbe} auf ${w.hintergrund})`
					);
				}
				if (w.istInk4) {
					zuSchwach.push(
						`${width}px · ${w.rolle}: Farbe ist --g-ink-4 (${w.farbe}) — laut ` +
							`Design-Leitprinzip nur fuer Placeholder/Disabled zulaessig`
					);
				}
			}
		}

		expect(
			zuSchwach,
			`AC-7 FAIL (Trip-Editor): Kontrast unter WCAG AA.\n  ${zuSchwach.join('\n  ')}`
		).toEqual([]);
	});

	test('AC-7: Ortsvergleich-Editor — dieselbe Zusicherung', async ({ page, request }) => {
		const presetId = await createVergleich(request);
		const panel = await oeffneVergleichsEditor(page, presetId);
		const legende = panel.locator(LEGENDE).first();

		const zuSchwach: string[] = [];
		for (const { width, height } of [BREITEN[0], BREITEN[BREITEN.length - 1]]) {
			await page.setViewportSize({ width, height });
			await page.waitForTimeout(250);
			const werte = await messeKontrast(legende);
			expect(werte.length, `AC-7: keine messbaren Legenden-Bestandteile bei ${width}px`)
				.toBeGreaterThan(0);
			berichteKontrast(`Vergleich ${width}px`, werte);
			for (const w of werte) {
				if (w.verhaeltnis < 4.5) {
					zuSchwach.push(
						`${width}px · ${w.rolle} ${JSON.stringify(w.text)}: ${w.verhaeltnis}:1 ` +
							`(${w.farbe} auf ${w.hintergrund})`
					);
				}
				if (w.istInk4) {
					zuSchwach.push(`${width}px · ${w.rolle}: Farbe ist --g-ink-4 (${w.farbe})`);
				}
			}
		}

		expect(
			zuSchwach,
			`AC-7 FAIL (Ortsvergleich): Kontrast unter WCAG AA.\n  ${zuSchwach.join('\n  ')}`
		).toEqual([]);
	});
});
