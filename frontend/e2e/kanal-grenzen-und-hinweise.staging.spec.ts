// E2E (Staging) — Issue #1719 S3 (echte Platzgrenzen im Trip-Editor) und #2438 (Abwahl-Hinweis im Trip-Editor).
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/14): die Kanal-Reiter der Metrik-Oberflaeche sind
// aus dem Reiter Zustellung entfernt. Im Hub zeigt die Karte „Was steht wo“ (Reiter Wetter) die Kanaele als Spalten:
//   AC-4: das SMS-Beispiel nennt die Zeichengrenze 160 (nicht „—“, nicht 140).
//   #2438 AC-1: der Hinweis, dass ein Kanal nur abwaehlt, was die Grundauswahl hat, steht im Kartentext.
//   AC-3 (Telegram-Grenze, #3375, ADR-0124 Nr. 3): beim Trip mit neun Metriken zeigt die Telegram-Spalte
//     „nur Tageswert“ genau bei der 8. und 9. Metrik (UV-Index, Sonnenscheindauer), Server-Antwort und Browser
//     stimmen ueberein; Gegenfall mit sieben Metriken ohne Marke. Die alte Kapplinie/Ueberlauf-Chip gibt es nicht mehr.
// Gestrichen:
//   AC-8 (global abgewaehlte Metrik erscheint im Kanal weder aktiv noch in der „Aus“-Gruppe): Ersatz
//     kanal-abwahl-bleibt-reversibel.staging.spec.ts AC-9 und ausblick-erbt-grundauswahl.staging.spec.ts AC-5
//     (keine Zeile ausserhalb der Grundauswahl).
//   #2438 AC-5 (320/375 px ohne Ueberlauf, Kontrast >= 4.5:1): Ersatz was-steht-wo-karte.spec.ts WS-8 (390 px,
//     keine seitliche Seite, jede Spalte erreichbar, Kontrast der Karte).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kanal-grenzen-und-hinweise.staging.spec.ts

import { test, expect, type Locator } from '@playwright/test';
import { markenStilVerstoesse, oeffneKarte, seedAbo, tabelle, zelle, type Abo, type Json } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.beforeEach(async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
});

test('AC-4: das SMS-Beispiel nennt die Zeichengrenze 160, nicht "—" und nicht "140"', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route');
	abos.push(abo);
	const karte = await oeffneKarte(page, 'route', abo.id);
	expect((await tabelle(page.request, 'route', abo.id)).sms_example.max_length).toBe(160);
	const zeichen = karte.getByTestId('was-steht-wo-sms-zeichen');
	await expect(zeichen).toContainText('von 160 Zeichen');
	await expect(zeichen).not.toContainText('140');
	await expect(zeichen).not.toContainText('—');
});

test('#2438 AC-1: der Kartentext erklaert, dass jede Spalte nur abwaehlt, was die Grundauswahl hat', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route');
	abos.push(abo);
	const karte = await oeffneKarte(page, 'route', abo.id);
	await expect(karte).toContainText('Jede Zeile ist eine Metrik aus der Auswahl oben.');
	await expect(karte).toContainText('Hier wählst du nur ab.');
});

// #3375 (Spec rework_3375_wsw_browserpruefungen.md AC-1..3): Telegram-Grenze ADR-0124 Nr. 3 im Browser.
// Bewoelkung heisst im Katalog `cloud_total`. Die Reihenfolge wird als `placements` mitgespeichert — ohne gespeicherte
// Tabelle ordnet der Server die Zeilen in Katalogfolge, und die 8./9. Metrik waeren andere.
const NEUN = ['temperature', 'gust', 'wind', 'precipitation', 'rain_probability', 'cloud_total', 'humidity', 'uv_index', 'sunshine'];
const tripMit = (metriken: string[]) => ({ metriken, dc: { placements: { version: 1, rows: metriken.map((metric_id) => ({ metric_id })) } } });
const NUR_TAGESWERT = 'nur Tageswert';

/** Alle Zellen der Server-Antwort mit Marke `nur_tageswert`, als `metrik/stelle`. */
function serverNurTageswert(antwort: Json): string[] {
	return (antwort.rows as Json[]).flatMap((r) =>
		Object.entries(r.cells as Record<string, Json>).filter(([, c]) => c?.mark === 'nur_tageswert').map(([stelle]) => `${r.metric_id}/${stelle}`)
	);
}

/** Alle sichtbaren Marken „nur Tageswert“ der Karte, als `metrik/stelle`. */
async function browserNurTageswert(karte: Locator): Promise<string[]> {
	return karte.locator('[data-slot="et-marke"]:visible', { hasText: NUR_TAGESWERT }).evaluateAll((ms) =>
		ms.map((m) => `${m.closest('[data-slot="et-zeile"]')?.getAttribute('data-metrik')}/${m.closest('[data-slot="et-zelle"]')?.getAttribute('data-stelle')}`)
	);
}

test('#3375 AC-1/AC-2: Trip mit neun Metriken — „nur Tageswert“ genau in den Telegram-Zellen von UV-Index und Sonnenscheindauer', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route', tripMit(NEUN));
	abos.push(abo);
	const karte = await oeffneKarte(page, 'route', abo.id);
	// AC-2: Server-Entscheidung zuerst — ein Fehlschlag ist so eindeutig Server oder Darstellung.
	expect(serverNurTageswert(await tabelle(page.request, 'route', abo.id)), 'Server-Antwort: Marke nur_tageswert').toEqual(['uv_index/telegram', 'sunshine/telegram']);
	// AC-1: sichtbar im Browser genau in diesen beiden Telegram-Zellen.
	for (const m of ['uv_index', 'sunshine']) {
		await expect(zelle(karte, m, 'telegram').locator('[data-slot="et-marke"]'), `Telegram-Zelle ${m}`).toHaveText(NUR_TAGESWERT);
		await expect(zelle(karte, m, 'telegram').locator('[data-slot="et-marke"]')).toBeVisible();
	}
	for (const m of NEUN.slice(0, 7)) await expect(zelle(karte, m, 'telegram'), `Telegram-Zelle ${m}`).not.toContainText(NUR_TAGESWERT);
	expect(await browserNurTageswert(karte), 'sichtbare Marken „nur Tageswert“ in der ganzen Karte').toEqual(['uv_index/telegram', 'sunshine/telegram']);
	// F001: toBeVisible laesst opacity:0 und transparente Schrift durch — berechneter Stil jeder Marke.
	expect(await markenStilVerstoesse(karte), 'Stil der Marken (visibility, Deckkraft, Schriftfarbe)').toEqual([]);
});

test('#3375 AC-3: Trip mit sieben Metriken — nirgends in der Karte „nur Tageswert“', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route', tripMit(NEUN.slice(0, 7)));
	abos.push(abo);
	const karte = await oeffneKarte(page, 'route', abo.id);
	expect(serverNurTageswert(await tabelle(page.request, 'route', abo.id)), 'Server-Antwort: Marke nur_tageswert').toEqual([]);
	// Die Telegram-Zellen sind an und bedienbar — dort koennte eine Marke stehen, sie fehlt also wirklich.
	for (const m of NEUN.slice(0, 7)) {
		await expect(zelle(karte, m, 'telegram'), `Telegram-Zelle ${m}`).toHaveAttribute('data-zustand', 'on');
		await expect(zelle(karte, m, 'telegram'), `Telegram-Zelle ${m}`).toHaveAttribute('data-bedienbar', 'true');
	}
	await expect(karte.getByText(NUR_TAGESWERT)).toHaveCount(0);
});
