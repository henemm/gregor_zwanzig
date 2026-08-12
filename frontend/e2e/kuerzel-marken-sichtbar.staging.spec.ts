// E2E (Staging) — Issue #1719 Scheibe S4: die Kuerzel-Marken im Bereich
// "Reihenfolge" bleiben in JEDER Fensterbreite vollstaendig lesbar.
//
// Spec: docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md
//   AC-5  zwei beschriftete Marken je Zeile, Kurzform mit ALLEN Kuerzeln
//   AC-10 fuenf Sichtbarkeits-Bedingungen, 14 Aufloesungen, ALLE Zeilen
//   AC-11 keine horizontale Seitenscroll-Leiste
//   AC-12 bei Platzmangel kuerzt der NAME, nie eine Marke
//   AC-13 dieselbe Zusicherung im Vergleichs-Editor
//   AC-14 die Ziehgeste ueberlebt die Layout-Aenderung
//
// PO-Vorgabe 2026-08-12 woertlich: "Stelle per Browser Tests sicher, dass alle
// Zeichen der Legende in unterschiedlichen Browserauflösungen sichtbar bleiben.
// Aktuell ist es etwas Glückssache."
//
// GEMESSENE URSACHE (Spec Abschnitt 4): `.label-cell` hat `min-width: 0` und
// darf unter die Inhaltsbreite schrumpfen; den Marken fehlt `flex-shrink: 0`.
// UNTER 900px rettet `flex-wrap: wrap` alles, AB 900px gibt es keinen Umbruch —
// die Bruchzone ist 900..~1300px. Der e2e-Bestand prueft 1280px und 390px,
// beide AUSSERHALB der Bruchzone. Die vorhandenen Testbreiten umgehen den
// Defekt systematisch, deshalb ist er nie aufgefallen.
//
// "Sichtbar" heisst hier GEOMETRISCH GEMESSEN, nicht "im DOM" — genau diese
// Verwechslung machte den Waechter aus #1453 blind.
//
// SCHREIBT NUR — laeuft in der RED-Phase NICHT (Staging traegt den alten
// Stand). Der Lauf gehoert in die GREEN-/Verifikationsphase.
//
// Ausfuehren (gegen Staging, aus frontend/, NACH Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.kuerzel-marken-sichtbar.staging.config.ts

import {
	test,
	expect,
	type APIRequestContext,
	type Locator,
	type Page
} from '@playwright/test';
import { createTestLocation } from './helpers';

const TRIP_ID = 'e2e-1719-s4-kuerzel';

/** Testids der beiden Marken. Gleichlautend im AST-Waechter
 *  src/lib/components/shared/__tests__/weather_metric_kuerzel_marken.test.ts. */
const MAIL_BADGE = '[data-testid="wm2-mail-badge"]';
const KURZFORM_BADGE = '[data-testid="wm2-kurzform-badge"]';

/** Sichtbare Beschriftung der Marken — beim Textvergleich abzuziehen. */
const BESCHRIFTUNGEN = ['Mail', 'Kurzform'];

/** Auflösungsmatrix aus der Spec, Abschnitt 4 — VERBINDLICH, keine Auswahl.
 *  Schwerpunkt auf der Bruchzone und beiden Raendern der Media-Query. */
const AUFLOESUNGEN = [
	{ klasse: 'Kleines Handy', width: 320, height: 568 },
	{ klasse: 'Kleines Handy', width: 375, height: 667 },
	{ klasse: 'Handy', width: 390, height: 844 },
	{ klasse: 'Handy', width: 414, height: 896 },
	{ klasse: 'Schmales Fenster', width: 600, height: 900 },
	{ klasse: 'Geteilter Bildschirm', width: 768, height: 1024 },
	{ klasse: 'Media-Query-Rand (unten)', width: 899, height: 900 },
	{ klasse: 'Media-Query-Rand (oben)', width: 901, height: 900 },
	{ klasse: 'Bruchzone', width: 960, height: 900 },
	{ klasse: 'Bruchzone', width: 1024, height: 768 },
	{ klasse: 'Bruchzone', width: 1180, height: 820 },
	{ klasse: 'Desktop', width: 1280, height: 900 },
	{ klasse: 'Desktop', width: 1440, height: 900 },
	{ klasse: 'Desktop', width: 1920, height: 1080 }
] as const;

/** Der Worst Case steht in der Liste, nicht eine bequeme Auswahl (Spec
 *  Abschnitt 4): "Gefuehlte Nacht-Tiefsttemperatur" ist mit 31 Zeichen der
 *  laengste Name im Katalog, "Gefuehlte Temperatur" traegt mit `FK FD WC` die
 *  laengste Kurzform. */
const TRIP_METRIKEN = [
	'wind_chill_night',
	'wind_chill',
	'temperature_night',
	'thunder',
	'humidity',
	'freezing_level'
];

const REPORT_CONFIG = {
	enabled: true,
	morning_enabled: true,
	evening_enabled: true,
	morning_time: '07:00:00',
	evening_time: '18:00:00',
	send_email: true,
	send_telegram: false,
	send_sms: false,
	multi_day_trend_morning: false,
	multi_day_trend_evening: true,
	multi_day_trend_reports: ['evening'],
	show_compact_summary: true,
	show_daylight: true,
	wind_exposition_min_elevation_m: null,
	show_stage_stats: true,
	show_quick_take_tags: true,
	show_stability: true,
	show_highlights: true,
	daily_summary_metrics: ['precipitation', 'wind', 'visibility', 'thunder'],
	show_metrics_summary: false,
	show_outlook: true,
	email_format: 'full',
	show_yesterday_comparison: true
};

const aufgeraeumt: { presets: string[]; orte: string[] } = { presets: [], orte: [] };

async function createTrip(request: APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E #1719 S4 Kuerzel-Marken',
			report_config: REPORT_CONFIG,
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

// ═══════════════════════════════════════════════════════════════════════════
// Erwartungswerte kommen aus dem BACKEND, nicht aus dieser Datei
//
// AC-6: "die Anzeige darf keine eigene Liste fuehren". Genau deshalb rechnet
// dieser Test die Erwartung aus derselben Quelle aus, aus der die Oberflaeche
// sie beziehen soll — waeren die Kuerzel hier abgetippt, koennten Anzeige und
// zugestellte Nachricht gemeinsam falsch und der Test trotzdem gruen sein.
// ═══════════════════════════════════════════════════════════════════════════

async function kurzformAusBackend(request: APIRequestContext): Promise<Record<string, string[]>> {
	const res = await request.get('/api/sms-symbols');
	expect(res.ok(), `/api/sms-symbols HTTP ${res.status()}`).toBeTruthy();
	const body = (await res.json()) as { metrics: { metric_id: string; sms_symbols: string[] }[] };
	return Object.fromEntries(body.metrics.map((m) => [m.metric_id, m.sms_symbols]));
}

async function mailKurzformAusBackend(request: APIRequestContext): Promise<Record<string, string>> {
	const res = await request.get('/api/metrics');
	expect(res.ok(), `/api/metrics HTTP ${res.status()}`).toBeTruthy();
	const body = (await res.json()) as Record<string, { id: string; col_label: string }[]>;
	const map: Record<string, string> = {};
	for (const gruppe of Object.values(body)) for (const m of gruppe) map[m.id] = m.col_label;
	return map;
}

async function compareKurzformAusBackend(
	request: APIRequestContext
): Promise<{ kurz: Record<string, string>; mail: Record<string, string> }> {
	const res = await request.get('/api/compare/metrics');
	expect(res.ok(), `/api/compare/metrics HTTP ${res.status()}`).toBeTruthy();
	const body = (await res.json()) as
		| { metric: string; sms_code: string; col_label: string }[]
		| { metrics: { metric: string; sms_code: string; col_label: string }[] };
	const liste = Array.isArray(body) ? body : body.metrics;
	const kurz: Record<string, string> = {};
	const mail: Record<string, string> = {};
	for (const e of liste) {
		kurz[e.metric] = e.sms_code;
		mail[e.metric] = e.col_label;
	}
	return { kurz, mail };
}

// ═══════════════════════════════════════════════════════════════════════════
// Die Messung: fuenf Bedingungen je Marke (Spec Abschnitt 4)
// ═══════════════════════════════════════════════════════════════════════════

type Befund = {
	groesse: string;
	marke: string;
	text: string;
	verletzt: string[];
};

/** Misst BEIDE Marken einer Zeile im echten Layout. Laeuft im Browser, weil
 *  nur dort `getBoundingClientRect`, `scrollWidth` und `elementFromPoint` die
 *  tatsaechliche Darstellung kennen. */
async function messeZeile(zeile: Locator): Promise<Befund[]> {
	await zeile.scrollIntoViewIfNeeded();
	return zeile.evaluate((row, { mailSel, kurzSel }) => {
		const befunde: {
			groesse: string;
			marke: string;
			text: string;
			verletzt: string[];
		}[] = [];
		const zeilenRect = row.getBoundingClientRect();
		const groesse = row.getAttribute('data-metric-id') ?? '(ohne data-metric-id)';
		const vw = window.innerWidth;

		for (const [name, sel] of [
			['Mail', mailSel],
			['Kurzform', kurzSel]
		] as const) {
			const marken = Array.from(row.querySelectorAll(sel)) as HTMLElement[];
			if (marken.length === 0) {
				befunde.push({
					groesse,
					marke: name,
					text: '',
					verletzt: [`0 Marke "${name}" fehlt in dieser Zeile (Selektor ${sel})`]
				});
				continue;
			}
			for (const el of marken) {
				const r = el.getBoundingClientRect();
				const text = (el.textContent ?? '').replace(/\s+/g, ' ').trim();
				const verletzt: string[] = [];

				if (r.width === 0 || r.height === 0) {
					verletzt.push(
						`0 Marke hat keine Ausdehnung (${r.width}x${r.height}) — sie ist ` +
							`ausgeblendet statt umgebrochen`
					);
				}
				// 1: Text nicht beschnitten
				if (el.scrollWidth > el.clientWidth + 1) {
					verletzt.push(
						`1 Text beschnitten: scrollWidth ${el.scrollWidth} > clientWidth ${el.clientWidth}`
					);
				}
				// 2: vollstaendig innerhalb ihrer Zeile
				if (
					r.left < zeilenRect.left - 1 ||
					r.right > zeilenRect.right + 1 ||
					r.top < zeilenRect.top - 1 ||
					r.bottom > zeilenRect.bottom + 1
				) {
					verletzt.push(
						`2 ragt aus der Zeile: Marke [${Math.round(r.left)},${Math.round(r.right)}]x` +
							`[${Math.round(r.top)},${Math.round(r.bottom)}], Zeile ` +
							`[${Math.round(zeilenRect.left)},${Math.round(zeilenRect.right)}]x` +
							`[${Math.round(zeilenRect.top)},${Math.round(zeilenRect.bottom)}]`
					);
				}
				// 3: vollstaendig im Sichtfenster (waagerecht)
				if (r.left < -1 || r.right > vw + 1) {
					verletzt.push(
						`3 ausserhalb des Sichtfensters: x ${Math.round(r.left)}..${Math.round(r.right)}, ` +
							`Fensterbreite ${vw}`
					);
				}
				// 4: nicht von einem Nachbarelement ueberdeckt
				const mitte = document.elementFromPoint(
					(r.left + r.right) / 2,
					(r.top + r.bottom) / 2
				);
				if (!mitte || !(mitte === el || el.contains(mitte))) {
					const wer = mitte
						? `<${mitte.tagName.toLowerCase()} class="${mitte.className}">`
						: 'nichts (Punkt liegt ausserhalb des Sichtfensters)';
					verletzt.push(`4 verdeckt: in der Mitte der Marke liegt ${wer}`);
				}
				// 5: kein Auslassungszeichen
				if (text.includes('…') || text.includes('...')) {
					verletzt.push(`5 Auslassungszeichen im Text: ${JSON.stringify(text)}`);
				}

				if (verletzt.length > 0) befunde.push({ groesse, marke: name, text, verletzt });
			}
		}
		return befunde;
	}, { mailSel: MAIL_BADGE, kurzSel: KURZFORM_BADGE });
}

/** Die Kuerzel einer Marke, ohne ihre Beschriftung. */
function kuerzelTokens(text: string): string[] {
	return text
		.split(/\s+/)
		.map((t) => t.trim())
		.filter((t) => t.length > 0 && !BESCHRIFTUNGEN.includes(t));
}

/** Bedingung 5 in ihrer strengen Form: der gerenderte Text IST das erwartete
 *  Kuerzel — nicht "enthaelt es irgendwo". */
async function pruefeTextgleichheit(
	zeile: Locator,
	selektor: string,
	erwartet: string[],
	wo: string
): Promise<string | null> {
	const roh = (await zeile.locator(selektor).first().textContent()) ?? '';
	const ist = kuerzelTokens(roh.replace(/\s+/g, ' ').trim());
	const gleich = ist.length === erwartet.length && ist.every((t, i) => t === erwartet[i]);
	return gleich
		? null
		: `${wo}: Marke zeigt [${ist.join(' ')}], das Backend fuehrt [${erwartet.join(' ')}]`;
}

// ═══════════════════════════════════════════════════════════════════════════
// Navigation
// ═══════════════════════════════════════════════════════════════════════════

async function oeffneTourenEditor(page: Page): Promise<Locator> {
	await page.goto(`/trips/${TRIP_ID}?tab=weather`);
	const reiter = page.getByTestId('trip-detail-tab-weather');
	await expect(reiter).toBeVisible({ timeout: 15_000 });
	await page.waitForLoadState('networkidle');
	await reiter.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 15_000 });
	await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
		timeout: 15_000
	});
	return tab;
}

async function oeffneVergleichsEditor(page: Page, presetId: string): Promise<Locator> {
	await page.goto(`/compare/${presetId}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
	await page.waitForLoadState('networkidle');
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 15_000 });
	return panel;
}

/** Pointer-Drag gegen `svelte-dnd-action` MIT Warten auf `finalize` — die
 *  Bibliothek feuert das Ereignis nach `mouseup` unzuverlaessig verzoegert
 *  (gemessen #1719 S3, 4 Laeufe: 2x gar nicht, 1x sofort, 1x nach ~1,9s). Eine
 *  feste Pause danach liest den `consider`-Zwischenstand und haelt ihn
 *  faelschlich fuer einen bestandenen Speichervorgang. Uebernommen aus
 *  wetter-metriken-vorschau-entfernt.staging.spec.ts. */
async function ziehe(page: Page, quelle: Locator, ziel: Locator): Promise<void> {
	await quelle.scrollIntoViewIfNeeded();
	await ziel.scrollIntoViewIfNeeded();
	const q = await quelle.boundingBox();
	const z = await ziel.boundingBox();
	if (!q || !z) throw new Error('ziehe: Quelle/Ziel ohne BoundingBox');

	await page.evaluate(() => {
		const zone = document.querySelector('.sortable-zone');
		if (!zone) throw new Error('ziehe: .sortable-zone nicht im DOM gefunden');
		(window as unknown as { __gzDndFinalize?: Promise<void> }).__gzDndFinalize = new Promise(
			(resolve) => zone.addEventListener('finalize', () => resolve(), { once: true })
		);
	});

	await page.mouse.move(q.x + q.width / 2, q.y + q.height / 2);
	await page.mouse.down();
	await page.mouse.move(q.x + q.width / 2, q.y + q.height / 2 - 12, { steps: 6 });
	await page.waitForTimeout(120);
	await page.mouse.move(z.x + z.width / 2, z.y + z.height / 2, { steps: 15 });
	await page.waitForTimeout(120);
	await page.mouse.up();

	const gefeuert = await page.evaluate(({ ms }) => {
		const w = window as unknown as { __gzDndFinalize?: Promise<void> };
		if (!w.__gzDndFinalize) return Promise.resolve(false);
		return Promise.race([
			w.__gzDndFinalize.then(() => true),
			new Promise<boolean>((r) => setTimeout(() => r(false), ms))
		]);
	}, { ms: 4_000 });
	if (!gefeuert) {
		throw new Error(
			'ziehe: finalize blieb aus (>4000ms) — die Ziehgeste hat nicht committet. ' +
				'Bekannte Flakiness des Pointer-Drag-Helfers (svelte-dnd-action), kein ' +
				'Produktfehler; Diagnose 2026-08-12 in #1719 S3.'
		);
	}
}

// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Issue #1719 S4: die Kuerzel-Marken sind lesbar, in jeder Fensterbreite', () => {
	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		for (const id of aufgeraeumt.presets) {
			await request.delete(`/api/compare/presets/${id}`).catch(() => {});
		}
		for (const id of aufgeraeumt.orte) {
			await request.delete(`/api/locations/${id}`).catch(() => {});
		}
	});

	// ── AC-5 / AC-6 ─────────────────────────────────────────────────────────
	test('AC-5: jede Zeile traegt beide Marken, die Kurzform mit ALLEN Kuerzeln', async ({
		page,
		request
	}) => {
		await createTrip(request);
		const kurz = await kurzformAusBackend(request);
		const mail = await mailKurzformAusBackend(request);

		await page.setViewportSize({ width: 1440, height: 900 });
		const tab = await oeffneTourenEditor(page);

		const abweichungen: string[] = [];
		for (const metricId of TRIP_METRIKEN) {
			const zeile = tab.locator(
				`[data-testid="wm2-reihenfolge-row"][data-metric-id="${metricId}"]`
			);
			await expect(
				zeile,
				`AC-5 FAIL: keine Reihenfolge-Zeile fuer '${metricId}' — Testaufbau pruefen`
			).toHaveCount(1);

			const erwarteteKurz = kurz[metricId];
			expect(
				erwarteteKurz,
				`Testaufbau: /api/sms-symbols kennt '${metricId}' nicht`
			).toBeTruthy();
			const f1 = await pruefeTextgleichheit(
				zeile,
				KURZFORM_BADGE,
				erwarteteKurz,
				`${metricId} / Kurzform`
			);
			if (f1) abweichungen.push(f1);

			const f2 = await pruefeTextgleichheit(
				zeile,
				MAIL_BADGE,
				[mail[metricId]],
				`${metricId} / Mail`
			);
			if (f2) abweichungen.push(f2);
		}

		expect(
			abweichungen,
			'AC-5/AC-6 FAIL: der Editor zeigt andere Kuerzel als die Kanaele senden.\n  ' +
				abweichungen.join('\n  ') +
				'\nBesonders hart: "Nacht-Tiefsttemperatur" — der Editor nennt heute ein ' +
				'Kuerzel, das in KEINER SMS vorkommt, waehrend das gesendete `N` nirgends ' +
				'erklaert wird.'
		).toEqual([]);
	});

	// ── AC-10 / AC-11 / AC-12 (Touren-Editor) ───────────────────────────────
	test('AC-10/AC-11: in allen 14 Aufloesungen erfuellt jede Marke jeder Zeile alle Bedingungen', async ({
		page,
		request
	}) => {
		await createTrip(request);
		const tab = await oeffneTourenEditor(page);

		const alleBefunde: string[] = [];
		for (const { klasse, width, height } of AUFLOESUNGEN) {
			await page.setViewportSize({ width, height });
			// Layout-Umbruch abwarten (Media-Query + Flex-Neuberechnung).
			await page.waitForTimeout(250);

			const zeilen = tab.locator('[data-testid="wm2-reihenfolge-row"]');
			const anzahl = await zeilen.count();
			if (anzahl !== TRIP_METRIKEN.length) {
				alleBefunde.push(
					`${width}x${height} (${klasse}): ${anzahl} statt ${TRIP_METRIKEN.length} ` +
						`Zeilen sichtbar — eine Groesse verschwindet bei dieser Breite`
				);
			}
			for (let i = 0; i < anzahl; i++) {
				for (const b of await messeZeile(zeilen.nth(i))) {
					for (const v of b.verletzt) {
						alleBefunde.push(
							`${width}x${height} (${klasse}) · ${b.groesse} · Marke "${b.marke}" ` +
								`(${JSON.stringify(b.text)}): ${v}`
						);
					}
				}
			}

			// AC-11: die Seite scrollt in dieser Breite nicht waagerecht.
			const scrollt = await page.evaluate(
				() => document.documentElement.scrollWidth > window.innerWidth + 1
			);
			if (scrollt) {
				const breite = await page.evaluate(() => document.documentElement.scrollWidth);
				alleBefunde.push(
					`${width}x${height} (${klasse}): AC-11 — die Seite scrollt waagerecht ` +
						`(scrollWidth ${breite} > innerWidth ${width})`
				);
			}
		}

		expect(
			alleBefunde,
			`AC-10/AC-11 FAIL — ${alleBefunde.length} Verletzungen:\n  ` + alleBefunde.join('\n  ')
		).toEqual([]);
	});

	// ── AC-12 ───────────────────────────────────────────────────────────────
	//
	// Gegenprobe (Spec, Pflicht): nimmt man den Marken die Unverkuerzbarkeit
	// wieder weg (`flex-shrink: 0` aus `.col-badge`/`.kurzform-badge` in
	// WeatherV2Reihenfolge.svelte entfernen — ODER dort `min-width: 0` bei
	// `.metric-label` streichen, das war der gemessene Auesloeser: ohne ihn
	// kann der NAME nicht schrumpfen und die Zelle holt sich den Platz bei den
	// Marken), MUSS dieser Test rot werden. Wird er es nicht,
	// bewacht er nichts. Die Gegenprobe laeuft an einem eigenen Staging-Stand;
	// dieser Test ist so gebaut, dass sie moeglich ist: er misst genau die
	// beiden Bedingungen, die eine schrumpfende Marke verletzt (1 und 5), und
	// erlaubt dem NAMEN ausdruecklich, gekuerzt zu sein.
	test('AC-12: in der Bruchzone kuerzt der Name, nie eine Marke', async ({ page, request }) => {
		await createTrip(request);
		const tab = await oeffneTourenEditor(page);

		const befunde: string[] = [];
		let irgendeinNameGekuerzt = false;
		for (const width of [960, 1024]) {
			await page.setViewportSize({ width, height: 900 });
			await page.waitForTimeout(250);

			const zeilen = tab.locator('[data-testid="wm2-reihenfolge-row"]');
			const anzahl = await zeilen.count();
			for (let i = 0; i < anzahl; i++) {
				const zeile = zeilen.nth(i);
				await zeile.scrollIntoViewIfNeeded();
				const messung = await zeile.evaluate((row, { mailSel, kurzSel }) => {
					const groesse = row.getAttribute('data-metric-id') ?? '?';
					const name = row.querySelector('.metric-label') as HTMLElement | null;
					const marken = [
						...Array.from(row.querySelectorAll(mailSel)),
						...Array.from(row.querySelectorAll(kurzSel))
					] as HTMLElement[];
					return {
						groesse,
						nameGekuerzt: name ? name.scrollWidth > name.clientWidth + 1 : false,
						marken: marken.map((el) => ({
							text: (el.textContent ?? '').replace(/\s+/g, ' ').trim(),
							beschnitten: el.scrollWidth > el.clientWidth + 1,
							scrollWidth: el.scrollWidth,
							clientWidth: el.clientWidth
						}))
					};
				}, { mailSel: MAIL_BADGE, kurzSel: KURZFORM_BADGE });

				if (messung.nameGekuerzt) irgendeinNameGekuerzt = true;
				for (const m of messung.marken) {
					if (m.beschnitten) {
						befunde.push(
							`${width}px · ${messung.groesse} · Marke ${JSON.stringify(m.text)} ist ` +
								`beschnitten (scrollWidth ${m.scrollWidth} > clientWidth ${m.clientWidth}) — ` +
								`gekuerzt werden darf der NAME, nie ein Kuerzel`
						);
					}
					if (m.text.includes('…') || m.text.includes('...')) {
						befunde.push(
							`${width}px · ${messung.groesse} · Marke traegt ein Auslassungszeichen: ` +
								JSON.stringify(m.text)
						);
					}
				}
			}
		}

		expect(befunde, `AC-12 FAIL:\n  ` + befunde.join('\n  ')).toEqual([]);
		// Rein diagnostisch, keine Zusicherung: ob der Name ueberhaupt kuerzen
		// MUSSTE, haengt an der Schriftgroesse des Staging-Browsers. Nur
		// protokolliert, damit ein spaeter gruener Lauf nicht faelschlich als
		// "Platz war reichlich, also ist nichts bewiesen" gelesen wird.
		test.info().annotations.push({
			type: 'AC-12',
			description: `Name in der Bruchzone gekuerzt: ${irgendeinNameGekuerzt}`
		});
	});

	// ── AC-13 (Vergleichs-Editor) ───────────────────────────────────────────
	test('AC-13: dieselbe Zusicherung im Vergleichs-Editor', async ({ page, request }) => {
		const ort1 = await createTestLocation(request, { name: 'S4 Nord', lat: 46.5, lon: 8.1 });
		const ort2 = await createTestLocation(request, { name: 'S4 Sued', lat: 46.9, lon: 8.4 });
		aufgeraeumt.orte.push(ort1.id, ort2.id);
		const angelegt = await request.post('/api/compare/presets', {
			data: {
				name: 'E2E #1719 S4 Kuerzel-Marken',
				location_ids: [ort1.id, ort2.id],
				schedule: 'daily',
				profil: 'wandern',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['urlauber@example.com'],
				display_config: {
					active_metrics: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h', 'humidity_avg_pct']
				}
			}
		});
		expect(angelegt.ok(), `Preset-Anlage HTTP ${angelegt.status()}`).toBeTruthy();
		const presetId = (await angelegt.json()).id as string;
		aufgeraeumt.presets.push(presetId);

		const { kurz, mail } = await compareKurzformAusBackend(request);
		const panel = await oeffneVergleichsEditor(page, presetId);

		const alleBefunde: string[] = [];
		for (const { klasse, width, height } of AUFLOESUNGEN) {
			await page.setViewportSize({ width, height });
			await page.waitForTimeout(250);

			const zeilen = panel.locator('[data-testid="wm2-reihenfolge-row"]');
			const anzahl = await zeilen.count();
			expect(anzahl, 'AC-13: keine Reihenfolge-Zeilen im Vergleichs-Editor').toBeGreaterThan(0);
			for (let i = 0; i < anzahl; i++) {
				const zeile = zeilen.nth(i);
				for (const b of await messeZeile(zeile)) {
					for (const v of b.verletzt) {
						alleBefunde.push(
							`${width}x${height} (${klasse}) · ${b.groesse} · Marke "${b.marke}" ` +
								`(${JSON.stringify(b.text)}): ${v}`
						);
					}
				}
				// Bedingung 5 streng, mit der Quelle des VERGLEICHS: die
				// Vergleichs-SMS rendert aus `get_sms_code()` — eine flaechenblinde
				// Korrektur auf die Trip-Kuerzel wuerde hier falsch anzeigen.
				const id = (await zeile.getAttribute('data-metric-id')) ?? '';
				if (kurz[id] !== undefined) {
					const f = await pruefeTextgleichheit(
						zeile,
						KURZFORM_BADGE,
						[kurz[id]],
						`${width}px · ${id} / Kurzform`
					);
					if (f) alleBefunde.push(f);
				}
				if (mail[id] !== undefined) {
					const f = await pruefeTextgleichheit(
						zeile,
						MAIL_BADGE,
						[mail[id]],
						`${width}px · ${id} / Mail`
					);
					if (f) alleBefunde.push(f);
				}
			}

			const scrollt = await page.evaluate(
				() => document.documentElement.scrollWidth > window.innerWidth + 1
			);
			if (scrollt) {
				alleBefunde.push(
					`${width}x${height} (${klasse}): AC-11/AC-13 — die Seite scrollt waagerecht`
				);
			}
		}

		expect(
			alleBefunde,
			`AC-13 FAIL — ${alleBefunde.length} Verletzungen im Vergleichs-Editor:\n  ` +
				alleBefunde.join('\n  ')
		).toEqual([]);
	});

	// ── AC-14 ───────────────────────────────────────────────────────────────
	test('AC-14: die Ziehgeste sortiert weiterhin um und speichert', async ({ page, request }) => {
		// PFLICHT, kein Nice-to-have: S3 hat in genau dieser Datei die Ziehgeste
		// lautlos zerbrochen (neue Array-Referenz im Zeilen-Markup), und 2553
		// Unit-Tests haben das nicht gesehen.
		await createTrip(request);
		await page.setViewportSize({ width: 1440, height: 900 });
		const tab = await oeffneTourenEditor(page);

		const zeilen = tab.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(zeilen).toHaveCount(TRIP_METRIKEN.length);
		const ersteVorher = await zeilen.first().getAttribute('data-metric-id');
		expect(ersteVorher).toBe(TRIP_METRIKEN[0]);

		const quelle = tab.locator(
			`[data-testid="wm2-reihenfolge-row"][data-metric-id="${TRIP_METRIKEN[2]}"]`
		);
		const ziel = tab.locator(
			`[data-testid="wm2-reihenfolge-row"][data-metric-id="${TRIP_METRIKEN[0]}"]`
		);
		await ziehe(page, quelle, ziel);

		await expect(zeilen.first()).toHaveAttribute('data-metric-id', TRIP_METRIKEN[2]);
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 15_000
		});

		// Ohne Neuladen waere das nur eine DOM-Bewegung: der lokale
		// `consider`-Zwischenstand sieht im selben Tab identisch aus.
		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		const neu = page
			.getByTestId('weather-metrics-tab')
			.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(
			neu.first(),
			'AC-14 FAIL: nach dem Neuladen steht die alte Reihenfolge — die Ziehgeste ' +
				'hat bewegt, aber nicht gespeichert'
		).toHaveAttribute('data-metric-id', TRIP_METRIKEN[2], { timeout: 10_000 });
	});
});
