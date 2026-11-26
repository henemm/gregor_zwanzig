// E2E (Staging) — Issue #1719 S4: die Kuerzel-Marken sind lesbar, in jeder Fensterbreite.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/12/14): die Reihenfolge-Listen je Kanal (Zeilen mit
// Roh/Kurzform-Marke, „Aus“-Zeile, Steuerung neben/unter dem Label) sind aus dem Reiter Zustellung entfernt. Im Hub
// zeigt die Karte „Was steht wo“ (Reiter Wetter) je Zeile und Stelle Haken, Roh/Einfach und Beispielwert; die
// Kuerzel stehen im SMS-Beispiel und unter „Kürzel erklärt“. Je Fall:
//   AC-14 (Ziehgeste sortiert und speichert, je Breite): umgezogen — Griff der Karte per Tastatur bei 390 und 901 px.
//   AC-5 (jede Zeile traegt Roh- und Kurzform-Marke mit allen Kuerzeln): gestrichen — die Kurzform-Marke gibt es nicht
//     mehr; Ersatz kuerzel-legende-lesbar.staging.spec.ts AC-1 (jedes Kuerzel einer SMS-Metrik erklaert) und
//     was-steht-wo-karte.spec.ts WS-2 (SMS-Beispiel folgt der Reihenfolge).
//   AC-10/AC-11 (14 Aufloesungen), AC-13 (Vergleich): umgezogen (#3375, Spec rework_3375_wsw_browserpruefungen.md
//     AC-4..6) — die Marken der Karte („nur Tageswert“, „passt nicht mehr“) sind bei allen 14 Aufloesungen von
//     320x568 bis 1920x1080 sichtbar, unbeschnitten, in ihrer Zeile und im Sichtfenster; die Seite scrollt nie seitlich.
//     Trip und Vergleich (3 Orte), je ein Seed, Breitenwechsel ohne Neuladen.
//   AC-12 (Bruchzone kuerzt den Namen, nie eine Marke): im Marken-Fall oben enthalten (Bruchzone 960/1024/1180).
//   AC-3/AC-5/AC-6 (Steuerung unter/neben dem Label, einzeilige „Aus“-Zeile): Wirkort ersatzlos entfallen (das
//     Zeilen-Layout der Kanal-Liste gibt es nicht mehr; „Aus“ ist ein Haken in der Spalte).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kuerzel-marken-sichtbar.staging.spec.ts

import { test, expect, type Locator, type Page } from '@playwright/test';
import { folge, markenStilVerstoesse, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, zeile, type Abo, type HubKind, type Json } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

for (const breite of [390, 901]) {
	test(`AC-14: die Ziehgeste (Griff, Tastatur) sortiert weiterhin um und speichert (${breite}px)`, async ({ page }) => {
		await page.setViewportSize({ width: breite, height: 900 });
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		const karte = await oeffneKarte(page, 'route', abo.id);
		const start = await folge(karte);
		const gespeichert = tabelleGespeichert(page, abo.id);
		await zeile(karte, start[0]).getByTestId('drag-handle').focus();
		await page.keyboard.press('Space');
		await page.keyboard.press('ArrowDown');
		await page.keyboard.press('Space');
		await gespeichert;
		const soll = [start[1], start[0], ...start.slice(2)];
		await expect.poll(() => folge(karte)).toEqual(soll);
		expect(((await tabelle(page.request, 'route', abo.id)).placements.rows as Array<{ metric_id: string }>).map((r) => r.metric_id)).toEqual(soll);
	});
}

// ═══ #3375 AC-4..6: Marken der Karte ueber 14 Aufloesungen ═══════════════════════════════════════════════════════

/** Aufloesungsmatrix der alten Fassung (fix_1719_s4 Abschnitt 4) — VERBINDLICH, keine Auswahl. */
const AUFLOESUNGEN = [
	{ width: 320, height: 568 },
	{ width: 375, height: 667 },
	{ width: 390, height: 844 },
	{ width: 414, height: 896 },
	{ width: 600, height: 900 },
	{ width: 768, height: 1024 },
	{ width: 899, height: 900 },
	{ width: 901, height: 900 },
	{ width: 960, height: 900 },
	{ width: 1024, height: 768 },
	{ width: 1180, height: 820 },
	{ width: 1280, height: 900 },
	{ width: 1440, height: 900 },
	{ width: 1920, height: 1080 }
] as const;

/** Die neun Metriken des Telegram-Falls (Telegram: „nur Tageswert“ ab der 8.) und dahinter neun weitere, damit das
 *  SMS-Beispiel die Grenze 160 reisst und „passt nicht mehr“ erscheint (mit neun Metriken allein: 92 Zeichen). */
const TRIP_MARKEN_METRIKEN = [
	'temperature', 'gust', 'wind', 'precipitation', 'rain_probability', 'cloud_total', 'humidity', 'uv_index', 'sunshine',
	'wind_chill', 'thunder', 'cape', 'snowfall_limit', 'freezing_level', 'pressure', 'dewpoint', 'cloud_low', 'visibility'
];
/** Vergleich: so viele Metriken, dass die SMS fuer drei Orte kuerzen muss (Zweig „passt nicht mehr“). */
const ORTE_MARKEN_METRIKEN = [
	'temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm', 'pop_max_pct', 'sunny_hours_h', 'cloud_avg_pct',
	'humidity_avg_pct', 'snowfall_limit_m', 'freezing_level_m', 'wind_chill_min_c', 'visibility_min_m', 'dewpoint_avg_c', 'pressure_avg_hpa'
];
const KARTEN_STELLEN = ['email', 'telegram', 'sms', 'hourly', 'outlook'];

/** Marken, die die Karte laut Server-Antwort zeigen muss (Zelle an, Stelle der Karte), als `metrik/stelle/mark`. */
function serverMarken(antwort: Json): string[] {
	return (antwort.rows as Json[]).flatMap((r) =>
		Object.entries(r.cells as Record<string, Json>)
			.filter(([stelle, c]) => KARTEN_STELLEN.includes(stelle) && c?.state === 'on' && c?.mark)
			.map(([stelle, c]) => `${r.metric_id}/${stelle}/${c.mark}`)
	);
}

/** Wartet, bis das Layout nach dem Breitenwechsel steht: Fensterbreite stimmt und zwei Messungen in Folge gleich. */
async function layoutSteht(page: Page, karte: Locator, breite: number): Promise<void> {
	let vorher = '';
	await expect
		.poll(async () => {
			const jetzt = await karte.evaluate((k) =>
				JSON.stringify([
					window.innerWidth,
					document.documentElement.scrollWidth,
					Math.round(k.getBoundingClientRect().width),
					...Array.from(k.querySelectorAll('[data-slot="et-marke"]')).map((m) => {
						const r = m.getBoundingClientRect();
						return [Math.round(r.width), Math.round(r.height)];
					})
				])
			);
			const steht = jetzt === vorher && JSON.parse(jetzt)[0] === breite;
			vorher = jetzt;
			return steht;
		}, { message: `Layout bei ${breite}px steht nicht`, intervals: [100, 200, 300], timeout: 10_000 })
		.toBe(true);
}

/** Misst jede Marke der Karte im echten Layout (Spec AC-4/AC-5); liefert Zahl der Marken und Verstoesse. */
async function messeMarken(karte: Locator): Promise<{ marken: string[]; verstoesse: string[] }> {
	return karte.evaluate((k) => {
		const marken: string[] = [];
		const verstoesse: string[] = [];
		const vw = window.innerWidth;
		for (const el of Array.from(k.querySelectorAll('[data-slot="et-marke"]')) as HTMLElement[]) {
			const row = el.closest('[data-slot="et-zeile"]') as HTMLElement;
			const id = `${row?.getAttribute('data-metrik')}/${el.closest('[data-slot="et-zelle"]')?.getAttribute('data-stelle')}`;
			const text = (el.textContent ?? '').trim();
			marken.push(`${id}/${text}`);
			row.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
			const r = el.getBoundingClientRect();
			const z = row.getBoundingClientRect();
			const v: string[] = [];
			if (r.width <= 0 || r.height <= 0) v.push(`keine Ausdehnung ${r.width}x${r.height}`);
			if (el.scrollWidth > el.clientWidth + 1) v.push(`Breite beschnitten: scrollWidth ${el.scrollWidth} > clientWidth ${el.clientWidth}`);
			if (el.scrollHeight > el.clientHeight + 1) v.push(`Hoehe beschnitten: scrollHeight ${el.scrollHeight} > clientHeight ${el.clientHeight}`);
			if (r.left < z.left - 1 || r.right > z.right + 1 || r.top < z.top - 1 || r.bottom > z.bottom + 1)
				v.push(`ragt aus der Zeile: Marke [${Math.round(r.left)},${Math.round(r.right)}]x[${Math.round(r.top)},${Math.round(r.bottom)}], Zeile [${Math.round(z.left)},${Math.round(z.right)}]x[${Math.round(z.top)},${Math.round(z.bottom)}]`);
			if (r.left < -1 || r.right > vw + 1) v.push(`ausserhalb des Sichtfensters: x ${Math.round(r.left)}..${Math.round(r.right)}, Fensterbreite ${vw}`);
			for (const t of v) verstoesse.push(`${id} „${text}“: ${t}`);
		}
		const sw = document.documentElement.scrollWidth;
		if (sw > window.innerWidth) verstoesse.push(`Seite laeuft seitlich ueber: scrollWidth ${sw} > innerWidth ${window.innerWidth}`);
		return { marken, verstoesse };
	});
}

/** Ein Seed, Breitenwechsel ueber alle 14 Aufloesungen; sammelt alle Verstoesse und prueft am Ende gemeinsam. */
async function markenUeberAlleBreiten(page: Page, kind: HubKind, abo: Abo, soll: string[]): Promise<void> {
	await page.setViewportSize({ width: AUFLOESUNGEN[0].width, height: AUFLOESUNGEN[0].height });
	const karte = await oeffneKarte(page, kind, abo.id);
	const befunde: string[] = [];
	for (const { width, height } of AUFLOESUNGEN) {
		await page.setViewportSize({ width, height });
		await layoutSteht(page, karte, width);
		const { marken, verstoesse } = await messeMarken(karte);
		verstoesse.push(...(await markenStilVerstoesse(karte))); // F001: sichtbar heisst auch visibility, Deckkraft, Schriftfarbe
		if (marken.length !== soll.length) befunde.push(`${width}x${height}: ${marken.length} Marken sichtbar, Server liefert ${soll.length} (${marken.join(', ')})`);
		for (const v of verstoesse) befunde.push(`${width}x${height}: ${v}`);
	}
	expect(befunde, 'Marken der Karte ueber 14 Aufloesungen').toEqual([]);
}

test('#3375 AC-4/AC-5: Trip — jede Marke der Karte ist bei 14 Aufloesungen sichtbar, unbeschnitten, in Zeile und Sichtfenster', async ({ page }) => {
	test.setTimeout(180_000);
	const abo = await seedAbo(page.request, 'route', {
		metriken: TRIP_MARKEN_METRIKEN,
		dc: { placements: { version: 1, rows: TRIP_MARKEN_METRIKEN.map((metric_id) => ({ metric_id })) } }
	});
	abos.push(abo);
	const soll = serverMarken(await tabelle(page.request, 'route', abo.id));
	expect(soll.some((m) => m.endsWith('/nur_tageswert')), `Server-Antwort traegt „nur Tageswert“: ${soll.join(', ')}`).toBe(true);
	expect(soll.some((m) => m.endsWith('/passt_nicht_mehr')), `Server-Antwort traegt „passt nicht mehr“: ${soll.join(', ')}`).toBe(true);
	await markenUeberAlleBreiten(page, 'route', abo, soll);
});

test('#3375 AC-6: Vergleich mit drei Orten — jede Marke der Karte ist bei 14 Aufloesungen sichtbar und unbeschnitten', async ({ page }) => {
	test.setTimeout(180_000);
	const abo = await seedAbo(page.request, 'vergleich', { orte: 3, metriken: ORTE_MARKEN_METRIKEN });
	abos.push(abo);
	const soll = serverMarken(await tabelle(page.request, 'vergleich', abo.id));
	expect(soll.length, 'Server-Antwort traegt mindestens eine Marke — sonst prueft der Fall nichts').toBeGreaterThan(0);
	const zweig = soll.some((m) => m.endsWith('/passt_nicht_mehr')) ? 'passt nicht mehr' : 'mindestens eine Marke';
	test.info().annotations.push({ type: 'Vergleichs-Zweig', description: `${zweig}: ${soll.join(', ')}` });
	await markenUeberAlleBreiten(page, 'vergleich', abo, soll);
});
