// TDD RED — Epic #1273 Slice S1: Compare-Hub bekommt den geteilten Save-Chip.
//
// Spec: docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md
//   § Acceptance Criteria AC-1, AC-2, AC-3, AC-4
//
// In der RED-Phase schlagen ALLE vier Tests fehl, weil `CompareTabs.svelte`
// (der Ortsvergleich-Hub unter /compare/[id]) heute KEINEN `<SaveIndicator>`
// rendert — `data-testid="save-indicator"` existiert dort schlicht nicht. Die
// Tests scheitern damit am `save-indicator`-Lookup (Timeout beim Warten auf das
// Element) — die ehrliche, erwartete RED-Ursache. Kein Mock, echter Klick-Pfad
// (Tab-Klick statt goto), Nachweis über `data-state`-Attribut (nicht Text-
// Matching) UND abgefangene PUT-Requests. Vorbild:
// save-status-indicator-honesty.spec.ts (#1269) + issue-758-save-indicator.spec.ts.
//
// Ausführen (Staging):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   cd frontend && npx playwright test \
//     --config=e2e/playwright.1273-s1.red.config.ts

import { test, expect, type Page, type Request } from '@playwright/test';

const PUT_URL_PART = '/api/compare/presets/';

/** Der geteilte Save-Chip: testid `save-indicator`, Zustand via `data-state`. */
function saveIndicator(page: Page) {
	return page.getByTestId('save-indicator');
}

/** Legt zwei Orte + ein Preset an, das beide vergleicht. Gibt IDs zurück. */
async function seedPreset(
	page: Page
): Promise<{ presetId: string; locIds: string[] }> {
	const suffix = Date.now();
	const locIds: string[] = [];
	for (const [name, lat, lon] of [
		[`E2E 1273 A ${suffix}`, 47.05, 11.05],
		[`E2E 1273 B ${suffix}`, 46.5, 11.35]
	] as const) {
		const res = await page.request.post('/api/locations', {
			data: { name, lat, lon }
		});
		expect(res.ok(), `Location-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
		locIds.push((await res.json()).id as string);
	}

	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name: `E2E 1273 ${suffix}`,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			morning_time: '07:00'
		}
	});
	expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
	return { presetId: (await presetRes.json()).id as string, locIds };
}

async function cleanup(page: Page, presetId: string, locIds: string[]) {
	await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	for (const id of locIds) await page.request.delete(`/api/locations/${id}`).catch(() => {});
}

/** Zeichnet jeden PUT auf das Preset auf. */
function collectPresetPuts(page: Page, presetId: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`${PUT_URL_PART}${presetId}`)) {
			puts.push(req);
		}
	});
	return puts;
}

test.describe('Epic #1273 S1 — Compare-Hub Save-Chip', () => {
	// AC-1: Hub öffnen → Chip zeigt sofort "✓ Gespeichert" (idle), kein
	// "Nicht gespeichert", kein "Speichere…".
	test('AC-1: Hub öffnen → Chip steht auf idle/"Gespeichert"', async ({ page }) => {
		const { presetId, locIds } = await seedPreset(page);
		try {
			await page.goto(`/compare/${presetId}`);
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });

			await expect(
				saveIndicator(page),
				'AC-1: der Ortsvergleich-Hub muss den geteilten Save-Chip rendern'
			).toBeVisible({ timeout: 10_000 });
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle');
			await expect(saveIndicator(page)).toContainText('Gespeichert');
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-2: echte Änderung (Ort entfernen) → Chip durchläuft saving → idle mit
	// neuem Zeitstempel; nach Reload bleibt der Ort entfernt (persistent).
	test('AC-2: Ort entfernen → Chip saving→idle mit Zeitstempel, Änderung persistent', async ({
		page
	}) => {
		const { presetId, locIds } = await seedPreset(page);
		try {
			await page.goto(`/compare/${presetId}?tab=orte`);
			await expect(page.getByTestId('compare-detail-panel-orte')).toBeVisible({ timeout: 10_000 });
			const rows = page.getByTestId('hub-orte-row');
			await expect(rows).toHaveCount(2);

			// Chip muss vor der Aktion existieren und "idle" zeigen.
			await expect(saveIndicator(page)).toBeVisible({ timeout: 10_000 });

			// Ersten Ort entfernen.
			await page.getByTestId('hub-orte-remove').first().click();

			// Chip durchläuft "saving" …
			await expect(
				saveIndicator(page),
				'AC-2: eine echte Änderung muss den Chip auf "Speichere…" (saving) schalten'
			).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			// … und landet wieder auf "idle" mit sichtbarem Zeitstempel.
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(saveIndicator(page).locator('.save-time')).toBeVisible();

			// Persistenz: nach Reload nur noch ein Ort.
			await page.reload();
			await expect(page.getByTestId('compare-detail-panel-orte')).toBeVisible({ timeout: 10_000 });
			await expect(page.getByTestId('hub-orte-row')).toHaveCount(1);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-3: Feld fokussieren/verlassen OHNE Änderung → Chip unverändert, NULL PUT
	// (Regressionsschutz gegen #1269 Speicher-Anzeige-Lüge).
	test('AC-3: Zahlenfeld fokussieren/verlassen ohne Änderung → Chip unverändert, kein PUT', async ({
		page
	}) => {
		const { presetId, locIds } = await seedPreset(page);
		const puts = collectPresetPuts(page, presetId);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${presetId}?tab=idealwerte`);
			await expect(page.getByTestId('compare-detail-panel-idealwerte')).toBeVisible({
				timeout: 10_000
			});
			await expect(page.getByTestId('corridor-editor-vergleich')).toBeVisible({ timeout: 10_000 });

			// Ausgangs-Chip merken (Text inkl. Zeitstempel).
			await expect(saveIndicator(page)).toBeVisible({ timeout: 10_000 });
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle');
			const before = (await saveIndicator(page).textContent()) ?? '';

			// Ein Zahlenfeld fokussieren und OHNE Änderung wieder verlassen.
			const field = page
				.getByTestId('corridor-editor-table')
				.locator('input[type="number"]')
				.first();
			await field.focus();
			await field.blur();
			await page.waitForTimeout(2_000);

			expect(
				puts.length,
				'AC-3: Fokussieren/Verlassen ohne Wertänderung darf keinen PUT auslösen'
			).toBe(0);
			expect(
				(await saveIndicator(page).textContent()) ?? '',
				'AC-3: der Chip (inkl. Zeitstempel) muss ohne echten Speichervorgang unverändert bleiben'
			).toBe(before);
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle');
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	// AC-4: PUT auf 500 stubben → Chip "Fehler beim Speichern" (error), UI-Feld
	// fällt auf den letzten persistierten Stand zurück (kein stiller Datenverlust).
	test('AC-4: PUT scheitert (500) → Chip zeigt "Fehler beim Speichern", Rollback', async ({
		page
	}) => {
		const { presetId, locIds } = await seedPreset(page);
		try {
			await page.goto(`/compare/${presetId}?tab=orte`);
			await expect(page.getByTestId('compare-detail-panel-orte')).toBeVisible({ timeout: 10_000 });
			await expect(page.getByTestId('hub-orte-row')).toHaveCount(2);
			await expect(saveIndicator(page)).toBeVisible({ timeout: 10_000 });

			// Den PUT auf das Preset gezielt auf 500 abwürgen.
			await page.route(`**${PUT_URL_PART}${presetId}`, (route) => {
				if (route.request().method() === 'PUT') {
					return route.fulfill({ status: 500, body: 'stubbed failure' });
				}
				return route.continue();
			});

			// Ort entfernen → PUT scheitert.
			await page.getByTestId('hub-orte-remove').first().click();

			await expect(
				saveIndicator(page),
				'AC-4: ein fehlgeschlagener PUT muss den Chip auf "Fehler" (error) schalten'
			).toHaveAttribute('data-state', 'error', { timeout: 10_000 });
			await expect(saveIndicator(page)).toContainText('Fehler beim Speichern');

			// Rollback: die beiden Orte sind wieder da (kein stiller Datenverlust).
			await expect(page.getByTestId('hub-orte-row')).toHaveCount(2);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});
});
