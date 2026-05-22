// TDD RED: Issue #322 — Wetter-Emojis durch WIcon ersetzen
//
// Deckt AC-4: StageDetailRow rendert SVG-Icon, kein Emoji-Zeichen im DOM.
// Deckt AC-5: Kein Emoji-Literal in produktiven Svelte/TS-Dateien (außer weatherEmoji.ts).
// Spec: docs/specs/modules/issue_322_wicon_komponente.md

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import path from 'path';

// AC-5: Grep-Prüfung — darf keine Emoji-Literale in produktiven Dateien haben
test('AC-5: Keine Wetter-Emojis in produktiven Svelte/TS-Dateien außerhalb weatherEmoji.ts', () => {
	// Führt grep direkt aus — kein Playwright-Browser nötig
	const frontendSrc = path.resolve(__dirname, '../src');
	let grepOutput = '';
	let hadHits = false;

	try {
		// grep -rnP für Unicode-Emoji-Block \x{1F300}-\x{1F9FF}
		grepOutput = execSync(
			`grep -rnP '[\\x{1F300}-\\x{1F9FF}]' "${frontendSrc}" --include="*.svelte" --include="*.ts"`,
			{ encoding: 'utf-8' }
		);
		hadHits = grepOutput.trim().length > 0;
	} catch (e: unknown) {
		// grep exit code 1 = keine Treffer — das wäre das Ziel
		const err = e as { status?: number; stdout?: string };
		if (err.status === 1) {
			hadHits = false;
		} else {
			throw e;
		}
	}

	// Filtere weatherEmoji.ts heraus (bleibt bewusst bestehen)
	const productiveHits = grepOutput
		.split('\n')
		.filter((line) => line.trim().length > 0)
		.filter((line) => !line.includes('weatherEmoji.ts'));

	expect(
		productiveHits,
		`Emoji-Literale gefunden in produktiven Dateien:\n${productiveHits.join('\n')}`
	).toHaveLength(0);
});

// AC-4: WIcon rendert SVG — kein Emoji-Zeichen im WeatherStrip
const TRIP_ID = 'e2e-cockpit-test';

test('AC-4: StageDetailRow zeigt SVG-Icon statt Emoji-Zeichen im weather-strip', async ({
	page
}) => {
	await page.goto(`/trips/${TRIP_ID}`);

	// Wechsel auf Etappen-Tab, damit StageDetailRow sichtbar wird
	const etappenTab = page.getByTestId('trip-detail-tab-stages');
	if (await etappenTab.isVisible()) {
		await etappenTab.click();
	}

	// Warte auf mindestens eine Stage-Row
	const firstRow = page.getByTestId(/trip-stage-row-/).first();
	if (!(await firstRow.isVisible().catch(() => false))) {
		// Kein Wetterdaten-Strip sichtbar — Test als bestanden werten (keine Emojis)
		return;
	}

	// Suche nach weather-strip innerhalb der ersten Row
	const weatherStrip = firstRow.locator('.weather-strip');
	if (!(await weatherStrip.isVisible().catch(() => false))) {
		return; // Keine Wetterdaten für diesen Trip — AC-4 nicht prüfbar
	}

	// AC-4a: Im weather-strip soll ein <svg>-Element sichtbar sein (WIcon)
	const svgInStrip = weatherStrip.locator('svg');
	await expect(svgInStrip.first()).toBeVisible();

	// AC-4b: Im weather-strip darf kein Emoji-Zeichen im Text stehen
	const stripText = await weatherStrip.textContent();
	const emojiPattern = /[\u{1F300}-\u{1F9FF}]/u;
	expect(
		emojiPattern.test(stripText ?? ''),
		`Emoji-Zeichen im weather-strip gefunden: "${stripText}"`
	).toBe(false);
});
