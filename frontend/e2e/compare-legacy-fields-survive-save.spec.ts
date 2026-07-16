// E2E — Issue #1268 (AC-3): Bestandsschutz der deprecateten Zeitfenster-Felder
// gegen den ECHTEN Go-Server.
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-3
//
// ── Warum dieser Test existiert (Adversary-Fund F004) ────────────────────────
// #1268 entfernt die Zeitfenster-/Horizont-Felder aus dem Editor. Die 158
// Bestands-Presets behalten ihre gespeicherten `hour_from`/`hour_to`/
// `forecast_hours` aber in der Persistenz. Der EINZIGE Mechanismus, der sie beim
// Speichern schuetzt, ist der Round-Trip-Spread `{ ...original, ... }` in
// `compareEditorSave.ts::buildComparePresetSavePayload`.
//
// Das wiegt schwer, weil der Go-Handler fuer diese Felder KEINEN
// Read-Modify-Write-Schutz hat (Adversary-Fund F003):
//   - `ForecastHours` hat einen (compare_preset.go:349-357: 0 → original → 48)
//   - `HourFrom`/`HourTo` haben KEINEN. Fehlen sie im PUT-Body, dekodiert Go sie
//     als Zero-Value 0 und schreibt 0. `validateComparePreset` laesst das durch
//     (0..23 erlaubt, und `HourTo < HourFrom` ist bei 0/0 falsch) — es gibt also
//     keinen Riegel. Der Datenverlust waere still.
//
// Ein Unit-Test auf `buildComparePresetSavePayload` (compare_save_deprecated_
// fields_roundtrip.test.ts) beweist nur, dass die reine Funktion die Werte in den
// Body legt — nicht, dass sie einen echten PUT gegen den echten Server
// ueberleben. Genau diesen Full-Stack-Nachweis liefert dieser Test: Wer den
// Spread entfernt, faellt hier auf.
//
// Vorlaeufer: `issue-1134-compare-timewindow-save.spec.ts` (mit #1268 geloescht,
// weil es die entfernten UI-Felder bediente). Dessen AC-3a-Waechter lebt hier
// weiter — ohne UI-Interaktion mit den Feldern, die es nicht mehr gibt.
//
// Base-URL: playwright.config.ts (Default localhost:4173 Preview; Staging via
// GZ_SVELTE_BASE analog bestehender Compare-E2E-Tests).
//
// Ausfuehren:
//   cd frontend && npx playwright test e2e/compare-legacy-fields-survive-save.spec.ts \
//     --config playwright.config.ts

import { test, expect, type Page, type Locator } from '@playwright/test';
import { login } from './helpers.js';

const saveIndicator = (page: Page): Locator => page.getByTestId('save-indicator');

/** Legt ein Preset mit explizit gesetzten Alt-Feldern an (echte Mandanten-Bindung). */
async function createLegacyPreset(
	page: Page
): Promise<{ id: string; empfaenger: string[] }> {
	const empfaenger = ['legacy-1268@example.com'];
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'Bestandsschutz-E2E 1268 ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			// Die deprecateten Felder bewusst auf NICHT-Default-Werte setzen, damit
			// ein Zurueckfallen auf 0 oder auf einen Default auffliegt.
			hour_from: 10,
			hour_to: 14,
			forecast_hours: 72,
			empfaenger
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	// Vorbedingung: der Server hat die Werte wirklich uebernommen — sonst prueft
	// der Test unten gegen Defaults und waere wertlos.
	expect(body.hour_from, 'Vorbedingung: hour_from=10 angelegt').toBe(10);
	expect(body.hour_to, 'Vorbedingung: hour_to=14 angelegt').toBe(14);
	expect(body.forecast_hours, 'Vorbedingung: forecast_hours=72 angelegt').toBe(72);
	return { id: body.id, empfaenger: body.empfaenger ?? empfaenger };
}

test.describe('Issue #1268: Bestandsfelder überleben einen echten Speichervorgang', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-3: reine Namensänderung lässt hour_from/hour_to/forecast_hours unverändert', async ({
		page
	}) => {
		// GIVEN: ein Bestands-Preset mit Zeitfenster 10–14 Uhr und Horizont 72 h
		const { id, empfaenger } = await createLegacyPreset(page);

		// WHEN: der Nutzer den Editor öffnet, NUR den Namen ändert und speichert.
		// Die Zeitfenster-/Horizont-Felder gibt es seit #1268 nicht mehr — der
		// Nutzer kann sie gar nicht anfassen. Genau das ist der Punkt: der PUT
		// darf sie trotzdem nicht nullen.
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		const neuerName = 'Nur-Name-1268 ' + Date.now();
		await page.locator('[data-testid="compare-editor-name"]').fill(neuerName);
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		// THEN: der echte Server hat die Alt-Werte unverändert behalten.
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();

		expect(preset.name, 'die Namensänderung muss angekommen sein').toBe(neuerName);
		expect(
			preset.hour_from,
			'hour_from muss 10 bleiben — Go hat KEINEN RMW-Schutz dafür (F003), der ' +
				'Round-Trip-Spread in compareEditorSave.ts ist der einzige Schutz'
		).toBe(10);
		expect(preset.hour_to, 'hour_to muss 14 bleiben (kein Nullen, kein Default)').toBe(14);
		expect(preset.forecast_hours, 'forecast_hours muss 72 bleiben').toBe(72);
		expect(preset.empfaenger, 'Empfänger dürfen nicht verloren gehen').toEqual(empfaenger);
	});

	test('AC-3: auch ein zweiter Speichervorgang nullt die Felder nicht (kein Drift)', async ({
		page
	}) => {
		// Waechter gegen schleichenden Verlust: Beim ersten Speichern kommt
		// `original` aus dem Server-Load, beim zweiten aus dem Zustand nach dem
		// ersten PUT. Faellt der erste PUT auf 0 zurueck, wuerde ein Test mit nur
		// einem Durchlauf es evtl. noch fangen — ein Drift ueber mehrere Speicher-
		// vorgaenge aber nicht.
		const { id } = await createLegacyPreset(page);

		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		for (const suffix of ['A', 'B']) {
			await page.locator('[data-testid="compare-editor-name"]').fill('Drift-1268-' + suffix);
			await page.locator('[data-testid="compare-editor-save"]').click();
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		}

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.hour_from, 'hour_from nach zwei Speichervorgängen').toBe(10);
		expect(preset.hour_to, 'hour_to nach zwei Speichervorgängen').toBe(14);
		expect(preset.forecast_hours, 'forecast_hours nach zwei Speichervorgängen').toBe(72);
	});
});
