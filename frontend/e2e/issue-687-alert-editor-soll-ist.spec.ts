// E2E-Tests fuer Issue #687 — Alert-Regel-Editor an #638 angleichen.
//
// Spec: docs/specs/modules/issue_687_alert_editor_soll_ist.md
//
// Soll-Ist: Der Editor (AlertRuleRow im Trip-Bearbeiten/-Anlegen/Wizard) wird
// an das #638-Karten-Modell angeglichen:
//   - KEINE Severity-Auswahl mehr (AC-1 Edit, AC-2 View)
//   - Kanal-Auswahl pro Alert, vorbelegt aus aktiven Briefing-Kanaelen (AC-3),
//     pro Alert ueberschreibbar mit DB-Roundtrip (AC-4)
//   - severity bleibt im Datensatz erhalten (AC-5)
//   - identisch im Trip-Anlegen (AC-6)
//
// Pattern (wie alert-rules-editor.spec.ts): Trip via API anlegen, Edit-Seite
// pruefen, Cleanup inline (DELETE).

import { test, expect } from '@playwright/test';

const TRIP_PREFIX = 'e2e-issue-687';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	alert_rules: unknown[] = [],
	report_config: Record<string, unknown> = { send_email: true, send_telegram: true, send_sms: false }
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 687 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config,
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

const ABS_RULE = {
	id: 'r1',
	kind: 'absolute',
	metric: 'wind_gust',
	threshold: 50,
	unit: 'km/h',
	severity: 'warning',
	enabled: true
};

async function openAlertsTab(page: import('@playwright/test').Page, id: string) {
	await page.goto(`/trips/${id}/edit`);
	await page.locator('[data-testid="edit-tabs"] [data-value="alarmregeln"]').click();
	await expect(page.locator('[data-testid="alert-rules-editor"]')).toBeVisible();
}

async function startEditFirstRule(page: import('@playwright/test').Page) {
	await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
	await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
	await expect(page.locator('[data-testid="alert-rule-edit"]')).toBeVisible();
}

test.describe('Issue #687: Alert-Editor Soll-Ist-Abgleich', () => {
	test('AC-1: Edit-Modus zeigt KEINE Severity-Auswahl mehr', async ({ page, request }) => {
		const id = tripId('ac1');
		await createTrip(request, id, [ABS_RULE]);
		try {
			await openAlertsTab(page, id);
			await startEditFirstRule(page);
			await expect(page.locator('[data-testid="alert-rule-severity"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-2: View-Modus zeigt keine Severity-Pill, aber die Modus-Pill (Abs/Δ)', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id, [ABS_RULE]);
		try {
			await openAlertsTab(page, id);
			const row = page.locator('[data-testid="alert-rule-row"]').first();
			await expect(row).toBeVisible();
			// Severity-Pill (tone=warning/info/critical) verschwunden ...
			await expect(row.locator('[data-slot="pill"][data-tone="warning"]')).toHaveCount(0);
			await expect(row.locator('[data-slot="pill"][data-tone="info"]')).toHaveCount(0);
			await expect(row.locator('[data-slot="pill"][data-tone="critical"]')).toHaveCount(0);
			// ... Modus-Pill (Abs) bleibt.
			await expect(row.locator('[data-slot="pill"][data-tone="default"]')).toContainText('Abs');
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-3: Kanal-Chips im Edit-Modus vorbelegt aus aktiven Briefing-Kanaelen', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		// report_config: email + telegram aktiv, sms aus -> Regel ohne eigene channels.
		await createTrip(request, id, [ABS_RULE]);
		try {
			await openAlertsTab(page, id);
			await startEditFirstRule(page);
			await expect(page.locator('[data-testid="alert-rule-channel-email"]')).toHaveAttribute(
				'aria-pressed',
				'true'
			);
			await expect(page.locator('[data-testid="alert-rule-channel-telegram"]')).toHaveAttribute(
				'aria-pressed',
				'true'
			);
			await expect(page.locator('[data-testid="alert-rule-channel-sms"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-4: Kanal abwaehlen + speichern persistiert (DB-Roundtrip)', async ({ page, request }) => {
		const id = tripId('ac4');
		await createTrip(request, id, [ABS_RULE]);
		try {
			await openAlertsTab(page, id);
			await startEditFirstRule(page);
			// Telegram abwaehlen (war geerbt-aktiv), dann speichern.
			await page.locator('[data-testid="alert-rule-channel-telegram"]').click();
			await page.locator('[data-testid="alert-rule-save"]').click();
			await expect(page.locator('[data-testid="alert-rule-edit"]')).toHaveCount(0);

			// Persistenz pruefen: API liefert nur noch email als channel.
			const res = await request.get(`/api/trips/${id}`);
			expect(res.ok()).toBeTruthy();
			const trip = await res.json();
			const rule = (trip.alert_rules ?? []).find((r: { id: string }) => r.id === 'r1') ?? trip.alert_rules[0];
			expect(rule.channels).toEqual(['email']);

			// Nach Reload zeigt der Editor Telegram inaktiv.
			await openAlertsTab(page, id);
			await startEditFirstRule(page);
			await expect(page.locator('[data-testid="alert-rule-channel-telegram"]')).toHaveAttribute(
				'aria-pressed',
				'false'
			);
			await expect(page.locator('[data-testid="alert-rule-channel-email"]')).toHaveAttribute(
				'aria-pressed',
				'true'
			);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-5: Bestands-severity bleibt nach Editor-Speichern erhalten (kein Datenverlust)', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		// Regel mit severity=info (frueher relevanter Wert).
		await createTrip(request, id, [{ ...ABS_RULE, severity: 'info' }]);
		try {
			await openAlertsTab(page, id);
			await startEditFirstRule(page);
			// Eine Kanal-Aenderung + speichern (loest den Save-Pfad aus).
			await page.locator('[data-testid="alert-rule-channel-telegram"]').click();
			await page.locator('[data-testid="alert-rule-save"]').click();
			await expect(page.locator('[data-testid="alert-rule-edit"]')).toHaveCount(0);

			const res = await request.get(`/api/trips/${id}`);
			const trip = await res.json();
			expect(trip.alert_rules.length).toBe(1);
			// severity bleibt im Datensatz erhalten (nur die UI-Auswahl wurde entfernt).
			expect(trip.alert_rules[0].severity).toBe('info');
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-6: Trip-Anlegen-Editor: keine Severity-Auswahl, Kanal-Chips vorhanden', async ({
		page
	}) => {
		await page.goto('/trips/new');
		// Zum Alerts-Bereich im Anlegen-Editor navigieren.
		await page.locator('[data-value="alarmregeln"]').first().click();
		await page.locator('[data-testid="alert-rules-editor-add"]').first().click();
		await page.locator('[data-testid="alert-rule-kebab-trigger"]').first().click();
		await page.locator('[data-testid="alert-rule-edit-btn"]').first().click();
		await expect(page.locator('[data-testid="alert-rule-edit"]')).toBeVisible();
		// Severity weg, Kanal-Chip vorhanden.
		await expect(page.locator('[data-testid="alert-rule-severity"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="alert-rule-channel-email"]')).toBeVisible();
	});
});
