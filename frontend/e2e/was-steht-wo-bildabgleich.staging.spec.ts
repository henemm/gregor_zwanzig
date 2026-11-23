// Abnahme — Issue #3283: Karte „Was steht wo“ (Reiter Wetter) gegen das Soll-Bild Fassung 4.
// Spec: docs/specs/modules/fix_3283_was_steht_wo_optik.md — AC-7 (SaveIndicator im Prüfaufbau ausgeblendet),
// AC-10 (sechs Aufnahmen für den `mockup-bildpruefer`), Grundlage für AC-1/AC-8/AC-9 im echten Browser.
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html (Kontextknöpfe data-ctx trip/orte/ort1).
//
// Drei Kontexte (Trip, drei Orte, ein Ort) × DE/EN, Element-Aufnahme der Karte bei 1280×900. Aufnahmen landen in
// docs/artifacts/fix-3283-wsw-optik/bilder/ (oder $BILD_DIR): mockup-<ctx>-de.png (Mockup nur Deutsch, per
// file://) und staging-<ctx>-<lang>.png. Der globale SaveIndicator („● Gespeichert“, position:fixed) ist kein
// Karteninhalt und wird im Prüfaufbau per CSS ausgeblendet (PO 23.11.2026: „So lassen“).
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste.
// Config (legt der Developer an, Vorlage playwright.2980-c2-bildabgleich.staging.config.ts mit
// testMatch /was-steht-wo-bildabgleich\.staging\.spec\.ts/):
//   cd frontend && npx playwright test --config playwright.3283-wsw-bildabgleich.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { oeffneKarte, seedAbo, type Abo, type HubKind } from './was-steht-wo.helpers';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const MOCKUP = 'file://' + path.resolve(HIER, '..', '..', 'docs', 'context', 'einstellungen_neu', 'seiten', 'mockup-hub-fassung4.html');
const ARTEFAKTE = path.resolve(HIER, '..', '..', 'docs', 'artifacts', 'fix-3283-wsw-optik', 'bilder');
const DESKTOP = { width: 1280, height: 900 };

type Lang = 'de' | 'en';
type Ctx = 'trip' | 'orte' | 'ort1';
const SPRACHEN: Lang[] = ['de', 'en'];
const KONTEXTE: { ctx: Ctx; kind: HubKind; orte?: number }[] = [
	{ ctx: 'trip', kind: 'route' },
	{ ctx: 'orte', kind: 'vergleich', orte: 3 },
	{ ctx: 'ort1', kind: 'vergleich', orte: 1 }
];
/** Grundauswahl mit Beispielwerten, die im Befund abgeschnitten waren (Luftfeuchte „61 %“, Wolken, Symbole),
 *  Fenster-Kindern (Temperatur, Gefühlte) und mehr als sieben Telegram-Metriken (Grenze „nur Tageswert“). */
const TRIP_METRIKEN = ['temperature', 'wind', 'gust', 'precipitation', 'thunder', 'wind_chill', 'cloud_total', 'humidity', 'rain_probability'];
const ORTE_METRIKEN = ['temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm', 'sunny_hours_h', 'cloud_avg_pct', 'humidity_avg_pct'];

/** Prüfaufbau: das globale „Gespeichert“-Etikett ragt sonst in die Element-Aufnahme (Befund 5). */
const OHNE_SAVE_INDICATOR = '[data-slot="save-indicator"], .save-indicator { display: none !important; }';

test.describe.configure({ mode: 'serial' });

function bildOrdner(): string {
	const d = process.env.BILD_DIR ?? ARTEFAKTE;
	mkdirSync(d, { recursive: true });
	return d;
}

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang}: HTTP ${res.status()}`).toBeTruthy();
}

test.afterAll(async ({ request }) => {
	await request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
});

// ── Mockup (Soll, nur Deutsch) ───────────────────────────────────────────────

test('#3283 Mockup: Karte „Was steht wo“ je Kontext (trip, orte, ort1)', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(MOCKUP);
	const ordner = bildOrdner();
	for (const { ctx } of KONTEXTE) {
		await page.evaluate((c) => document.querySelector<HTMLElement>(`[data-ctx="${c}"]`)?.click(), ctx);
		const karte = page.locator('[data-abschnitt="was-steht-wo"]').first();
		await expect(karte, `Mockup ${ctx}: Karte fehlt`).toBeVisible();
		await karte.screenshot({ path: path.join(ordner, `mockup-${ctx}-de.png`) });
	}
});

// ── Staging (Ist) ────────────────────────────────────────────────────────────

for (const { ctx, kind, orte } of KONTEXTE) {
	for (const lang of SPRACHEN) {
		test(`#3283 Staging ${ctx} ${lang}: Element-Aufnahme der Karte ohne Gespeichert-Etikett`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await sprache(page, lang);
			let abo: Abo | null = null;
			try {
				abo = await seedAbo(page.request, kind, { metriken: kind === 'route' ? TRIP_METRIKEN : ORTE_METRIKEN, orte });
				const karte = await oeffneKarte(page, kind, abo.id);
				await page.addStyleTag({ content: OHNE_SAVE_INDICATOR });
				await expect(page.locator('[data-slot="save-indicator"]:visible, .save-indicator:visible'), 'AC-7: Etikett im Prüfaufbau sichtbar').toHaveCount(0);
				// Legende aufklappen, damit der Bildprüfer Befund 7 sieht.
				const legende = karte.locator('[data-testid="was-steht-wo-legende-auf"]').first();
				if (await legende.isVisible()) await legende.click();

				// AC-1: kein Beispielwert in den Kanalspalten abgeschnitten (berechnete Breite = Inhaltsbreite).
				const abgeschnitten = await karte.locator('[data-slot="et-beispiel"]:visible').evaluateAll((els) =>
					els.filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.textContent)
				);
				expect(abgeschnitten, 'AC-1: abgeschnittene Beispielwerte').toEqual([]);
				// AC-2: Zusatzspalten ohne Beispielwert.
				const zusatz = karte.locator('[data-slot="et-zelle"][data-stelle="outlook"] [data-slot="et-beispiel"], [data-slot="et-zelle"][data-stelle="hourly"] [data-slot="et-beispiel"]');
				await expect(zusatz, 'AC-2: Beispielwert in Stundenverlauf/Ausblick').toHaveCount(0);

				await karte.screenshot({ path: path.join(bildOrdner(), `staging-${ctx}-${lang}.png`) });
			} finally {
				await abo?.aufraeumen();
			}
		});
	}
}
