// E2E-Tests fuer Issue #223 — AlertRulesEditor in TripEditView.
//
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md
//
// Pattern: Trip wird via API angelegt, danach Edit-Seite geprueft.
// Cleanup inline am Ende jedes Tests (DELETE /api/trips/<id>).

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-223';

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
			name: `Issue 223 ${id}`,
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
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

test.describe('Issue #223: AlertRulesEditor', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-1: Empty-State bei leerem alert_rules', async ({ page, request }) => {
		const id = tripId('ac1');
		await createTrip(request, id, []);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await expect(page.locator('[data-testid="alert-rules-editor"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rules-editor-empty"]')).toContainText(
				'Noch keine Alarmregeln'
			);
			await expect(page.locator('[data-testid="alert-rules-editor-add"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-2: View-Mode zeigt Label, Threshold und Severity-Pill', async ({ page, request }) => {
		const id = tripId('ac2');
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
			const row = page.locator('[data-testid="alert-rule-row"]');
			await expect(row).toHaveCount(1);
			await expect(row.first()).toContainText('Böen');
			await expect(row.first()).toContainText('> 50');
			await expect(row.first()).toContainText('km/h');
			await expect(
				row.first().locator('[data-slot="pill"][data-tone="warning"]')
			).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-3: Add-Button erzeugt Default-Rule im View-Mode', async ({ page, request }) => {
		const id = tripId('ac3');
		await createTrip(request, id, []);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await page.locator('[data-testid="alert-rules-editor-add"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]');
			await expect(row).toHaveCount(1);
			await expect(row.first()).toContainText('Böen');
			await expect(row.first()).toContainText('> 50 km/h');
			// View-Mode aktiv → Edit-Felder NICHT sichtbar
			await expect(page.locator('[data-testid="alert-rule-edit"]')).not.toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-4: Löschen entfernt Rule, Empty-State erscheint wieder', async ({ page, request }) => {
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
			await page.locator('[data-testid="alert-rule-delete"]').first().click();
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="alert-rules-editor-empty"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-5: Bearbeiten + Threshold ändern + Speichern → View-Mode mit neuem Wert', async ({
		page,
		request
	}) => {
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
			await expect(page.locator('[data-testid="alert-rule-edit"]')).toBeVisible();
			const thresholdInput = page.locator('[data-testid="alert-rule-threshold"]').first();
			await thresholdInput.fill('60');
			await page.locator('[data-testid="alert-rule-save"]').click();
			await expect(page.locator('[data-testid="alert-rule-edit"]')).not.toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-row"]').first()).toContainText('> 60');
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-6: Abbrechen verwirft Änderung', async ({ page, request }) => {
		const id = tripId('ac6');
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
			await page.locator('[data-testid="alert-rule-threshold"]').first().fill('99');
			await page.locator('[data-testid="alert-rule-cancel"]').click();
			await expect(page.locator('[data-testid="alert-rule-edit"]')).not.toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-row"]').first()).toContainText('> 50');
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-7: Save-Roundtrip — Add → Save → Reload zeigt die Rule', async ({ page, request }) => {
		const id = tripId('ac7');
		await createTrip(request, id, []);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await page.locator('[data-testid="alert-rules-editor-add"]').click();
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(1);

			const putPromise = page.waitForRequest(
				(req) => req.method() === 'PUT' && req.url().endsWith(`/api/trips/${id}`)
			);
			await page.locator('[data-testid="edit-save-btn"]').click();
			const putReq = await putPromise;
			const body = JSON.parse(putReq.postData() || '{}');
			expect(Array.isArray(body.alert_rules)).toBe(true);
			expect(body.alert_rules.length).toBe(1);
			expect(body.alert_rules[0].metric).toBe('wind_gust');

			await page.waitForURL('/trips', { timeout: 5000 });

			// Reload: Rule muss persistiert sein
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(1);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-8: AlertsPreviewCard hat Edit-Link auf /trips/[id]/edit#alerts', async ({
		page,
		request
	}) => {
		const id = tripId('ac8');
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
			await page.goto(`/trips/${id}`);
			const link = page.locator('[data-testid="right-card-alerts-edit-link"]');
			await expect(link).toBeVisible();
			await expect(link).toHaveAttribute('href', `/trips/${id}/edit#alerts`);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-9: Enabled-Toggle wirkt ohne Edit-Mode', async ({ page, request }) => {
		const id = tripId('ac9');
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
			const toggle = page.locator('[data-testid="alert-rule-row"] input[type="checkbox"]').first();
			await expect(toggle).toBeChecked();
			await toggle.click();
			await expect(toggle).not.toBeChecked();
			// Edit-Mode wurde NICHT aktiviert
			await expect(page.locator('[data-testid="alert-rule-edit"]')).not.toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-10: THUNDER_LEVEL — View zeigt "HOCH", Edit zeigt Select mit MITTEL/HOCH', async ({
		page,
		request
	}) => {
		const id = tripId('ac10');
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'thunder_level',
				threshold: 2.0,
				unit: '',
				severity: 'critical',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-section-alerts-header"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			await expect(row).toContainText('HOCH');
			await expect(row).not.toContainText('> 2');

			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			const select = page.locator('[data-testid="alert-rule-threshold"]').first();
			await expect(select).toBeVisible();
			// Tag-Name verifizieren: select (nicht number-input)
			const tag = await select.evaluate((el) => el.tagName.toLowerCase());
			expect(tag).toBe('select');
			await expect(select.locator('option')).toHaveCount(2);
			await expect(select.locator('option', { hasText: 'MITTEL' })).toHaveCount(1);
			await expect(select.locator('option', { hasText: 'HOCH' })).toHaveCount(1);
		} finally {
			await deleteTrip(request, id);
		}
	});
});
