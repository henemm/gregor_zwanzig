// E2E-Tests fuer Issue #223 — AlertRulesEditor in TripEditView.
//
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md
//
// Pattern: Trip wird via API angelegt, danach Edit-Seite geprueft.
// Cleanup inline am Ende jedes Tests (DELETE /api/trips/<id>).
//
// Issue #319: Kebab-Öffnen vor Edit/Delete-Klicks vorgeschaltet.
// Neue AC-1 bis AC-6 Tests für Kebab-Menü am Ende der Datei.

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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
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

	// Issue #319: Kebab-Trigger öffnen vor Delete-Klick
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-delete"]').first().click();
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="alert-rules-editor-empty"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
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

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
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

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			await expect(row).toContainText('HOCH');
			await expect(row).not.toContainText('> 2');

			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
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

test.describe('Issue #297: AlertRulesEditor — mode=both mit zwei Threshold-Feldern', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
	test('AC-3: mode=both zeigt drei separate Felder (abs + delta + zeitfenster)', async ({ page, request }) => {
		const id = tripId('ac297-3');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			await expect(page.locator('[data-testid="alert-rule-edit"]')).toBeVisible();
			// mode='both' wählen
			await page.locator('[data-testid="mode-card-both"]').click();
			// Drei separate Felder müssen erscheinen
			await expect(page.locator('[data-testid="alert-rule-threshold-abs"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-threshold-delta"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-delta-window"]')).toBeVisible();
			// Das generische threshold-Feld darf NICHT vorhanden sein wenn mode='both'
			await expect(page.locator('[data-testid="alert-rule-threshold"]')).not.toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
	test('AC-9: Speichern-Button zeigt "Beide Regeln speichern" bei mode=both', async ({ page, request }) => {
		const id = tripId('ac297-9');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			// Erst Speichern-Button bei mode='absolute' prüfen
			await expect(page.locator('[data-testid="alert-rule-save"]')).toContainText('Speichern');
			await expect(page.locator('[data-testid="alert-rule-save"]')).not.toContainText('Beide Regeln speichern');
			// mode='both' wählen
			await page.locator('[data-testid="mode-card-both"]').click();
			// Button-Label muss sich ändern
			await expect(page.locator('[data-testid="alert-rule-save"]')).toContainText('Beide Regeln speichern');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
	test('AC-10: Nach Speichern mit mode=both erscheint pair-indicator bei zweiter Rule', async ({ page, request }) => {
		const id = tripId('ac297-10');
		await createTrip(request, id, []);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			// Neue Rule hinzufügen
			await page.locator('[data-testid="alert-rules-editor-add"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			// mode='both' wählen
			await page.locator('[data-testid="mode-card-both"]').click();
			// Threshold-Felder füllen
			await page.locator('[data-testid="alert-rule-threshold-abs"]').fill('80');
			await page.locator('[data-testid="alert-rule-threshold-delta"]').fill('30');
			// Speichern
			await page.locator('[data-testid="alert-rule-save"]').click();
			// Zwei Zeilen müssen erscheinen
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(2);
			// Zweite Zeile hat pair-indicator
			await expect(page.locator('[data-testid="pair-indicator"]')).toHaveCount(1);
			await expect(page.locator('[data-testid="alert-rule-row"]').nth(1).locator('[data-testid="pair-indicator"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Issue #319: Kebab-Trigger öffnen vor Edit-Klick
	test('AC-4: ModeCard "Beides" zeigt Badge "3 Felder"', async ({ page, request }) => {
		const id = tripId('ac297-4');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
			// ModeCard 'both' muss Badge "3 Felder" zeigen
			await expect(page.locator('[data-testid="mode-card-badge-both"]')).toBeVisible();
			await expect(page.locator('[data-testid="mode-card-badge-both"]')).toContainText('3 Felder');
			// Auch die anderen ModeCards prüfen
			await expect(page.locator('[data-testid="mode-card-badge-absolute"]')).toContainText('1 Feld');
			await expect(page.locator('[data-testid="mode-card-badge-delta"]')).toContainText('2 Felder');
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-11: pair_id und delta_window überleben PUT-Roundtrip (Backend-Persistenz)', async ({ page, request }) => {
		const id = tripId('ac297-11');
		await createTrip(request, id, [
			{
				id: 'r-abs',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 80,
				unit: 'km/h',
				severity: 'warning',
				enabled: true,
				pair_id: 'test-pair-uuid-123'
			},
			{
				id: 'r-delta',
				kind: 'delta',
				metric: 'wind_gust',
				threshold: 30,
				unit: 'km/h',
				severity: 'warning',
				enabled: true,
				pair_id: 'test-pair-uuid-123',
				delta_window: '3h'
			}
		]);
		try {
			// Trip via API neu laden und Felder prüfen
			const res = await request.get(`/api/trips/${id}`);
			expect(res.status()).toBe(200);
			const body = await res.json();
			const rules: unknown[] = body.alert_rules ?? [];
			expect(rules).toHaveLength(2);
			const absRule = (rules as Array<{kind: string; pair_id?: string; delta_window?: string}>)
				.find(r => r.kind === 'absolute');
			const deltaRule = (rules as Array<{kind: string; pair_id?: string; delta_window?: string}>)
				.find(r => r.kind === 'delta');
			expect(absRule?.pair_id).toBe('test-pair-uuid-123');
			expect(deltaRule?.pair_id).toBe('test-pair-uuid-123');
			expect(deltaRule?.delta_window).toBe('3h');
		} finally {
			await deleteTrip(request, id);
		}
	});
});

// Issue #319: Kebab-Menü für AlertRuleRow
// Spec: docs/specs/modules/issue_319_alert_rule_kebab_menu.md
//
// TDD RED — diese Tests müssen fehlschlagen, da data-testid="alert-rule-kebab-trigger"
// noch nicht im DOM existiert (Implementierung noch ausstehend).

test.describe('Issue #319: Kebab-Menue (AC-1 bis AC-6)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-1: Keine direkten Edit/Delete-Buttons sichtbar im View-Modus, nur Kebab-Trigger
	test('AC-1: View-Modus zeigt nur Kebab-Trigger, keine direkten Bearbeiten/Loeschen-Buttons', async ({
		page,
		request
	}) => {
		const id = tripId('ac319-1');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			// Kebab-Trigger muss sichtbar sein
			await expect(row.locator('[data-testid="alert-rule-kebab-trigger"]')).toBeVisible();
			// Direkte Text-Buttons duerfen NICHT sichtbar sein
			await expect(row.locator('[data-testid="alert-rule-edit-btn"]')).not.toBeVisible();
			await expect(row.locator('[data-testid="alert-rule-delete"]')).not.toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-2: Klick auf Kebab-Trigger oeffnet Dropdown mit Bearbeiten + Loeschen
	test('AC-2: Klick auf Kebab-Trigger oeffnet Dropdown mit Bearbeiten und Loeschen', async ({
		page,
		request
	}) => {
		const id = tripId('ac319-2');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			// Vor Klick: Dropdown-Eintraege nicht sichtbar
			await expect(page.locator('[data-testid="alert-rule-edit-btn"]')).not.toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-delete"]')).not.toBeVisible();
			// Klick auf Trigger
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			// Dropdown muss sichtbar sein (role=menu)
			await expect(page.locator('[role="menu"]')).toBeVisible();
			// Beide Eintraege sichtbar
			await expect(page.locator('[data-testid="alert-rule-edit-btn"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-delete"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-3: Klick auf Bearbeiten im Dropdown oeffnet Edit-Modus
	test('AC-3: Dropdown Bearbeiten oeffnet Edit-Modus', async ({ page, request }) => {
		const id = tripId('ac319-3');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-edit-btn"]').click();
			// Dropdown geschlossen
			await expect(page.locator('[role="menu"]')).not.toBeVisible();
			// Edit-Modus aktiv: Threshold-Input und Speichern-Button sichtbar
			await expect(page.locator('[data-testid="alert-rule-edit"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-save"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-4: Klick auf Loeschen im Dropdown entfernt die Regel
	test('AC-4: Dropdown Loeschen entfernt die Regel', async ({ page, request }) => {
		const id = tripId('ac319-4');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			await page.locator('[data-testid="alert-rule-delete"]').click();
			// Regel entfernt
			await expect(page.locator('[data-testid="alert-rule-row"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="alert-rules-editor-empty"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-5: Escape-Taste schliesst das Dropdown
	test('AC-5: Escape-Taste schliesst das offene Dropdown', async ({ page, request }) => {
		const id = tripId('ac319-5');
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
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
			// Dropdown ist offen
			await expect(page.locator('[role="menu"]')).toBeVisible();
			// Escape druecken
			await page.keyboard.press('Escape');
			// Dropdown geschlossen
			await expect(page.locator('[role="menu"]')).not.toBeVisible();
			// Trigger noch sichtbar
			await expect(page.locator('[data-testid="alert-rule-kebab-trigger"]').first()).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-6: F004-Fallback-Pfad zeigt nur Kebab-Trigger, keinen direkten Loeschen-Button
	test('AC-6: F004-Fallback zeigt Kebab-Trigger statt direktem Loeschen-Button', async ({
		page,
		request
	}) => {
		const id = tripId('ac319-6');
		// Unbekannte Metrik loest F004-Fallback aus
		await createTrip(request, id, [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'unknown_metric_xyz',
				threshold: 10,
				unit: '',
				severity: 'warning',
				enabled: true
			}
		]);
		try {
			await page.goto(`/trips/${id}/edit`);
			await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			// Kebab-Trigger muss sichtbar sein
			await expect(row.locator('[data-testid="alert-rule-kebab-trigger"]')).toBeVisible();
			// Kein direkter Loeschen-Button
			await expect(row.locator('[data-testid="alert-rule-delete"]')).not.toBeVisible();
			// Dropdown oeffnen: nur Loeschen, kein Bearbeiten
			await row.locator('[data-testid="alert-rule-kebab-trigger"]').click();
			await expect(page.locator('[data-testid="alert-rule-delete"]')).toBeVisible();
			await expect(page.locator('[data-testid="alert-rule-edit-btn"]')).not.toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});
});
