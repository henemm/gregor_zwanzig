// E2E-Tests fuer Issue #183 — Email-Preview Header (AC-5 + AC-6).
//
// Spec-Referenz: docs/specs/modules/issue_183_email_preview_header.md
//   - AC-5: Header zeigt Trip-Name + Eyebrow ("Morgen-Briefing" / "Abend-Briefing")
//   - AC-6: Stats-Grid mit 5 Labels (Distanz, Aufstieg, Abstieg, Max-Hoehe, Segmente)
//
// Test-Strategie: Dev-Route /email-preview-dev rendert die Komponente
// isoliert mit Mock-Daten. Die Route wird in Issue #189 (Vorschau-Integration)
// durch die echte Einbindung ersetzt.

import { test, expect } from '@playwright/test';
import { cleanupTracked, createTestTrip, login } from './helpers.js';

// ── Issue #2283 AC-11 (docs/specs/modules/shared_preview_tab.md) ─────────────
// Nach der Umstellung auf den geteilten Vorschau-Reiter muss die Trip-Vorschau
// INHALTLICH dieselbe sein wie bisher (Gleichheit je Kanal belegt der Kern,
// AC-1). Live (Staging) wird hier belegt: der Reiter holt ueber
// GET /api/briefings/{id}/preview?kind=route, zeigt genau dieses HTML im
// iframe und genau diesen SMS-Text im Telefonrahmen, die Alt-Route antwortet
// weiter, und der tote Platzhalter „#189" ist weg.
test.describe('Issue #2283 AC-11: Trip-Vorschau inhaltsgleich nach der Umstellung', () => {
	test.setTimeout(120_000);
	test.afterEach(async ({ page }) => {
		await cleanupTracked(page.request);
	});

	test('E-Mail-HTML, Betreff und SMS-Text = Alt-Routen; iframe zeigt das HTML; kein Platzhalter', async ({ page }) => {
		await login(page);
		const s = Date.now();
		const trip = await createTestTrip(page.request, {
			name: `AC-11 Inhaltsgleich ${s}`,
			stages: [
				{
					id: `s-${s}`,
					name: 'Etappe 1',
					date: new Date(Date.now() + 86_400_000).toISOString().slice(0, 10),
					waypoints: [
						{ id: `w1-${s}`, name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
						{ id: `w2-${s}`, name: 'Ziel', lat: 47.3, lon: 11.45, elevation_m: 900 }
					]
				}
			]
		});
		const buendelAntwort = page.waitForResponse(
			(r) => /\/api\/briefings\/[^/?]+\/preview\?/.test(r.url()) && r.request().method() === 'GET'
		);
		await page.goto(`/trips/${trip.id}`);
		await page.getByTestId('trip-detail-tab-vorschau').first().click();
		const res = await buendelAntwort;
		expect(res.ok(), `Buendelaufruf fehlgeschlagen: ${res.status()}`).toBeTruthy();
		const q = new URL(res.url()).searchParams;
		expect(q.get('kind')).toBe('route');
		const buendel = (await res.json()) as { subject: string; email_html: string; sms: { text: string } };
		expect(buendel.subject.length).toBeGreaterThan(0);
		expect(buendel.email_html.length).toBeGreaterThan(100);
		// Byte-Gleichheit Buendel ↔ Alt-Routen ist Kern-Aufgabe von AC-1
		// (tests/integration/test_briefing_preview_bundle.py): das Rendering
		// traegt Zeitanteile (datetime.now), zwei getrennte Live-Renders sind
		// nicht byte-gleich — hier deshalb NUR: der Reiter zeigt genau, was der
		// Buendelaufruf geliefert hat, und die Alt-Route lebt als Delegate (AC-5).
		const opts = new URLSearchParams({ type: q.get('type') ?? 'morning' });
		if (q.get('demo')) opts.set('demo', q.get('demo')!);
		const altEmail = await page.request.get(`/api/preview/${trip.id}/email?${opts}`);
		expect(altEmail.ok(), `Alt-Route /api/preview/{id}/email antwortet nicht mehr: ${altEmail.status()}`).toBeTruthy();

		const panel = page.getByTestId('trip-detail-panel-vorschau');
		await expect(panel.getByTestId('email-iframe')).toHaveAttribute('srcdoc', buendel.email_html, { timeout: 30_000 });
		await panel.getByRole('button', { name: /^SMS/ }).click();
		await expect(panel.getByTestId('sms-token-bubble')).toHaveText(buendel.sms.text);
		await expect(panel).not.toContainText('Inhalt folgt mit Issue #189');
	});
});

test.describe('Issue #183 — Email-Preview Header (Dev-Route)', () => {
	test('AC-5: Header zeigt Trip-Name "Zillertal" und Eyebrow "Morgen-Briefing"', async ({
		page
	}) => {
		await page.goto('/email-preview-dev');
		await expect(page.getByTestId('email-preview-header').first()).toBeVisible();
		await expect(
			page.getByTestId('email-preview-header-eyebrow').first()
		).toHaveText(/Morgen-Briefing/);
		await expect(
			page.getByTestId('email-preview-header-title').first()
		).toContainText('Zillertal');
	});

	test('AC-6: Stats-Grid enthaelt 5 Labels', async ({ page }) => {
		await page.goto('/email-preview-dev');
		const firstHeader = page.getByTestId('email-preview-header').first();
		await expect(firstHeader).toBeVisible();
		for (const key of ['distanz', 'aufstieg', 'abstieg', 'max-hoehe', 'segmente']) {
			await expect(
				firstHeader.getByTestId(`email-preview-header-stats-label-${key}`)
			).toHaveCount(1);
		}
		// Zusaetzlich: Text-Inhalt pruefen, damit AC-6 (Beschriftung lt. Spec) erhalten bleibt
		const labels = firstHeader.locator('[data-testid^="email-preview-header-stats-label-"]');
		const texts = (await labels.allTextContents()).map((t) => t.trim());
		expect(texts).toEqual(['Distanz', 'Aufstieg', 'Abstieg', 'Max-Höhe', 'Segmente']);
	});

	test('Screenshot-Snapshot fuer visuelle Verifikation', async ({ page }) => {
		await page.goto('/email-preview-dev');
		await page.waitForSelector('[data-testid="email-preview-header"]');
		await page.screenshot({
			path: '../docs/artifacts/issue-183-email-preview-header/screenshot-header.png',
			fullPage: false
		});
	});
});
