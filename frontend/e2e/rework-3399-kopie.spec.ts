// E2E (Staging) — Issue #3399 S2, AC-5: „Vergleich als Kopie" (/compare/new?from=<id>) zeigt im
// Schritt Wetter die Vorlage, die der SERVER fuer die Quelle aufloest (POST /api/ampel/aufloesung),
// nicht eine im Frontend errechnete.
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md (Test Plan „Live", AC-5).
//
// Soll: der Test stellt die Aufloesung der Quelle selbst (angemeldete Sitzung). Ist: die im
// Vorlagen-Picker als aktiv markierte Option (`data-aktiv="true"`). Wegwerf-Daten (Praefix E2E-GZ-),
// kein fester Schlaf, nie gegen Produktion.
//
//   cd frontend && npx playwright test --config playwright.3399.staging.config.ts rework-3399-kopie

import { test, expect } from '@playwright/test';
import { ANLEGE_SEL, cleanupTracked, createTestComparePreset, createTestLocation, E2E_TEST_PREFIX } from './helpers';
import { DESKTOP } from './s3b2795-zustellung.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';
const SEL = ANLEGE_SEL.vergleich;

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

test('AC-5: Kopie eines Vergleichs zeigt im Schritt Wetter die vom Server aufgelöste Vorlage der Quelle', async ({ page }) => {
	const suffix = Date.now();
	const l1 = await createTestLocation(page.request, { name: `${E2E_TEST_PREFIX}R3399K-O1-${suffix}`, lat: 47.2, lon: 11.4 });
	const l2 = await createTestLocation(page.request, { name: `${E2E_TEST_PREFIX}R3399K-O2-${suffix}`, lat: 47.3, lon: 11.5 });
	const q = await createTestComparePreset(page.request, {
		name: `${E2E_TEST_PREFIX}R3399K-Quelle-${suffix}`,
		locationIds: [l1.id, l2.id],
		profil: 'wintersport'
	});

	// Soll: Aufloesung der gespeicherten Quelle (wie die Seite sie stellt: eintragAusAbo).
	const quelle = (await (await page.request.get(`/api/compare/presets/${q.id}`)).json()) as {
		profil?: string;
		display_config?: { ampel?: unknown; preset_name?: unknown } | null;
	};
	const dc = quelle.display_config ?? {};
	const eintrag = {
		ampel: dc.ampel ?? null,
		preset_name: typeof dc.preset_name === 'string' ? dc.preset_name : null,
		profil: typeof quelle.profil === 'string' ? quelle.profil : null
	};
	const antwort = await page.request.post(AUFLOESUNG, { data: { eintraege: [eintrag] } });
	expect(antwort.ok(), `Aufloesung HTTP ${antwort.status()}`).toBeTruthy();
	const soll = ((await antwort.json()) as { ergebnisse: { vorlage_id: string }[] }).ergebnisse[0]?.vorlage_id;
	expect(soll, 'Server liefert eine Vorlagen-ID').toBeTruthy();
	expect(soll, 'Messaufbau: Quelle muss eine Vorlage ungleich „allgemein" tragen').not.toBe('allgemein');

	// Ist: Kopie oeffnen, Schritt Wetter, aktive Option im Vorlagen-Picker.
	await page.setViewportSize(DESKTOP);
	await page.goto(`/compare/new?from=${q.id}`);
	await expect(SEL.name(page)).toHaveValue(new RegExp(`R3399K-Quelle-${suffix}`), { timeout: 15_000 });
	await SEL.reiter(page, 'wetter').click();
	await expect.poll(async () => (await SEL.zustand(SEL.reiter(page, 'wetter'))).aktiv, { timeout: 10_000 }).toBe(true);

	const wetter = SEL.inhalt['wetter-metriken'](page);
	const picker = wetter.getByTestId('wetter-vorlage-picker');
	await expect(picker, 'Vorlagen-Picker fehlt im Schritt Wetter').toBeVisible({ timeout: 15_000 });
	await picker.click();
	const aktiv = wetter.locator('[data-testid^="wetter-vorlage-option-"][data-aktiv="true"]');
	await expect(aktiv, 'genau eine Vorlage vorausgewaehlt').toHaveCount(1, { timeout: 10_000 });
	const ist = ((await aktiv.getAttribute('data-testid')) ?? '').replace('wetter-vorlage-option-', '');
	expect(ist, `Kopie zeigt „${ist}" statt der Server-Vorlage „${soll}" der Quelle`).toBe(soll);
});
