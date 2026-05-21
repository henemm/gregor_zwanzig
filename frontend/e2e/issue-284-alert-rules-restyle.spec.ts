// TDD RED — Issue #284: AlertRulesEditor + ModeCard Restyle
// Spec: docs/specs/modules/issue_284_alert_rules_restyle.md
//
// Diese Tests prüfen visuelle und strukturelle Eigenschaften nach dem Restyle.
// Alle Tests MÜSSEN rot sein vor der Implementierung.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-284';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	alert_rules: unknown[] = []
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 284 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }
					]
				}
			],
			alert_rules
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string
) {
	await request.delete(`/api/trips/${id}`);
}

test.describe('Issue #284: AlertRulesEditor Restyle', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-2: Severity-Pill zeigt deutschen Label und ist outlined
	test('AC-2a: Severity-Pill zeigt "Warnung" statt "warning"', async ({ page, request }) => {
		const id = tripId('ac2a');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			// MUSS rot sein: "Warnung" ist noch nicht implementiert (zeigt "warning")
			await expect(row).toContainText('Warnung');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-2: Severity-Pill ist outlined (data-outlined Attribut vorhanden)
	test('AC-2b: Severity-Pill hat data-outlined Attribut', async ({ page, request }) => {
		const id = tripId('ac2b');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			// MUSS rot sein: data-outlined ist noch nicht implementiert
			await expect(
				row.locator('[data-slot="pill"][data-tone="warning"][data-outlined]')
			).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-2: Severity-Pill hat transparenten Hintergrund (outlined statt gefüllt)
	test('AC-2c: Severity-Pill hat transparenten Hintergrund', async ({ page, request }) => {
		const id = tripId('ac2c');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const pill = page
				.locator('[data-testid="alert-rule-row"]')
				.first()
				.locator('[data-slot="pill"][data-tone="warning"]');
			const bg = await pill.evaluate((el) => getComputedStyle(el).backgroundColor);
			// MUSS rot sein: currently background-color ist gefüllt (--g-warning), nicht transparent
			expect(bg).toBe('rgba(0, 0, 0, 0)');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-3: Kind-Badge (Abs/Δ) ist ebenfalls outlined
	test('AC-3: Kind-Badge hat data-outlined Attribut', async ({ page, request }) => {
		const id = tripId('ac3');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			// MUSS rot sein: Kind-Badge hat noch kein data-outlined
			await expect(
				row.locator('[data-slot="pill"][data-tone="default"][data-outlined]')
			).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-1: Speichern-Button ist <Btn> (data-slot="btn") mit variant="primary"
	test('AC-1a: Speichern-Button ist Btn-Komponente (data-slot=btn)', async ({ page, request }) => {
		const id = tripId('ac1a');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			const saveBtn = page.locator('[data-testid="alert-rule-save"]');
			// MUSS rot sein: aktuell plain <button class="btn-primary">, kein data-slot="btn"
			await expect(saveBtn).toHaveAttribute('data-slot', 'btn');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-1: Abbrechen-Button ist <Btn> mit variant="ghost"
	test('AC-1b: Abbrechen-Button ist Btn ghost (data-variant=ghost)', async ({ page, request }) => {
		const id = tripId('ac1b');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			const cancelBtn = page.locator('[data-testid="alert-rule-cancel"]');
			// MUSS rot sein: aktuell plain <button class="btn-secondary">
			await expect(cancelBtn).toHaveAttribute('data-variant', 'ghost');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-1: Bearbeiten-Button in View-Mode ist <Btn> ghost
	test('AC-1c: Bearbeiten-Button ist Btn ghost (data-slot=btn)', async ({ page, request }) => {
		const id = tripId('ac1c');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const editBtn = page.locator('[data-testid="alert-rule-edit-btn"]').first();
			// MUSS rot sein: aktuell plain <button class="btn-secondary">
			await expect(editBtn).toHaveAttribute('data-slot', 'btn');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-7: Add-Button ist <Btn> (data-slot="btn") mit variant="ghost"
	test('AC-7a: Add-Button ist Btn ghost (data-slot=btn)', async ({ page, request }) => {
		const id = tripId('ac7a');
		await createTrip(request, id, []);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const addBtn = page.locator('[data-testid="alert-rules-editor-add"]');
			// MUSS rot sein: aktuell plain <button class="add-button">
			await expect(addBtn).toHaveAttribute('data-slot', 'btn');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-5: ModeCard example-Text ist nicht kursiv
	test('AC-5: ModeCard example-Text ist Mono-Font, nicht kursiv', async ({ page, request }) => {
		const id = tripId('ac5');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			// ModeCard (absolut) ist standard-ausgewählt
			const modeCard = page.locator('[data-testid="mode-card-absolute-selected"]');
			await expect(modeCard).toBeVisible();
			// Example-Text: .example span suchen
			// MUSS rot sein: aktuell font-style: italic
			const fontStyle = await modeCard.evaluate((el) => {
				const example = el.querySelector('.example');
				return example ? getComputedStyle(example).fontStyle : 'not-found';
			});
			expect(fontStyle).toBe('normal');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-4: Threshold-Wert nutzt Mono-Font
	test('AC-4: Threshold-Wert hat JetBrains Mono font-family', async ({ page, request }) => {
		const id = tripId('ac4');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			// MUSS rot sein: .threshold hat aktuell keinen Mono-Font definiert
			const fontFamily = await row.evaluate((el) => {
				const threshold = el.querySelector('.threshold');
				return threshold ? getComputedStyle(threshold).fontFamily : 'not-found';
			});
			expect(fontFamily).toContain('JetBrains Mono');
		} finally {
			await deleteTrip(request, id);
		}
	});
});
