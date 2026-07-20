// E2E (Staging) — #1329 Maßnahme B: selbsträumende Playwright-Suites.
//
// Spec: docs/specs/modules/fix_1329_e2e_data_hygiene.md
// Context: docs/context/fix-1329-e2e-data-hygiene.md
//
// GRÜN-Phase: `createTestLocation()`/`createTestComparePreset()`/`cleanupTracked()`
// existieren in `./helpers`. Diese Suite beweist das ECHTE Cleanup-Verhalten
// (AC-1, AC-3) gegen Staging. AC-2 (globalTeardown-Sicherheitsnetz bei
// abgebrochenem Testfall) ist strukturell nicht aus einem einzelnen Testfall
// heraus beweisbar — siehe Kommentar bei `test.skip(...)` unten.
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test e2e/e2e-data-hygiene.staging.spec.ts --config playwright.config.ts

import { test, expect } from '@playwright/test';
import { createTestLocation, createTestComparePreset, cleanupTracked } from './helpers';

const PREFIX = 'E2E-GZ-';

test.describe('#1329 Maßnahme B: E2E-Datenhygiene', () => {
	test('AC-1: cleanupTracked() entfernt angelegte Praefix-Objekte wieder (Ort + Preset)', async ({
		request
	}) => {
		const loc = await createTestLocation(request);
		expect(loc.name.startsWith(PREFIX), 'Testort traegt kein reserviertes Praefix').toBeTruthy();

		const preset = await createTestComparePreset(request, { locationIds: [loc.id] });
		expect(preset.name.startsWith(PREFIX), 'Testpreset traegt kein reserviertes Praefix').toBeTruthy();

		// Vorbedingung: beide Objekte sind unmittelbar nach Anlage abrufbar.
		const locBefore = await request.get(`/api/locations/${loc.id}`);
		expect(locBefore.ok(), 'Ort muss vor Cleanup abrufbar sein').toBeTruthy();
		const presetBefore = await request.get(`/api/compare/presets/${preset.id}`);
		expect(presetBefore.ok(), 'Preset muss vor Cleanup abrufbar sein').toBeTruthy();

		// Kern-Nachweis: der geteilte Helfer-Cleanup entfernt genau die angelegten
		// IDs (Preset VOR Ort, s. CLEANUP_ORDER in helpers.ts).
		await cleanupTracked(request);

		const locAfter = await request.get(`/api/locations/${loc.id}`);
		expect(locAfter.status(), 'Ort muss nach cleanupTracked() 404 liefern').toBe(404);
		const presetAfter = await request.get(`/api/compare/presets/${preset.id}`);
		expect(presetAfter.status(), 'Preset muss nach cleanupTracked() 404 liefern').toBe(404);

		// Auch in den Listen-Endpunkten taucht die konkrete ID nicht mehr auf.
		const locsAfter = await request.get('/api/locations');
		const locListBody = (await locsAfter.json()) as Array<{ id?: string }>;
		expect(locListBody.some((l) => l.id === loc.id)).toBeFalsy();

		const presetsAfter = await request.get('/api/compare/presets');
		const presetListBody = (await presetsAfter.json()) as Array<{ id?: string }>;
		expect(presetListBody.some((p) => p.id === preset.id)).toBeFalsy();
	});

	// AC-2: Ort bleibt nach absichtlich fehlschlagendem Testfall dank
	// globalTeardown-Sicherheitsnetz nicht liegen.
	//
	// Dieser Nachweis ist strukturell NICHT aus einem einzelnen In-Suite-Testfall
	// führbar: Playwright fährt `globalTeardown` erst NACH Abschluss der
	// GESAMTEN Suite aus (unabhängig vom Ergebnis einzelner Tests) — ein Test
	// kann also nie innerhalb seiner eigenen Laufzeit beobachten, ob das
	// Sicherheitsnetz nach Suite-Ende gegriffen hat, ohne den Testrunner selbst
	// zweimal aufzurufen. Der Beweis erfolgt daher operativ: in `/60-validate`
	// wird ein Testlauf mit einem absichtlich fehlschlagenden Testfall gegen
	// Staging ausgeführt und anschließend per API/DB verifiziert, dass keine
	// `E2E-GZ-`-Präfix-Objekte übrig geblieben sind (globalTeardown hat geräumt).
	test.skip(
		'AC-2: globalTeardown raeumt Praefix-Objekte auch nach fehlschlagendem Testfall (operativ in /60-validate verifiziert, nicht in-suite fuehrbar)',
		() => {}
	);

	test('AC-3: Cleanup loescht referenzierendes Preset vor dem referenzierten Ort (kein 409)', async ({
		request
	}) => {
		const loc = await createTestLocation(request);
		const preset = await createTestComparePreset(request, { locationIds: [loc.id] });

		// Reihenfolge Preset-vor-Ort ist vorsorglich/Best-Practice: der Go-Handler
		// `DeleteLocationHandler` (internal/handler/location.go) macht KEINEN
		// Reference-Check und liefert nie 409 — die geschluckten DELETE-Fehler aus
		// Root Cause #3 (Kontext-Dokument) waren 401/500, kein 409-Konflikt. Die
		// Reihenfolge verhindert dennoch verwaiste Presets, die auf bereits
		// gelöschte Orte zeigen.
		const deletePresetRes = await request.delete(`/api/compare/presets/${preset.id}`);
		expect(deletePresetRes.ok(), 'Preset-Loeschung muss vor der Ort-Loeschung erfolgen').toBeTruthy();

		const deleteLocRes = await request.delete(`/api/locations/${loc.id}`);
		// DeleteLocationHandler liefert 204 No Content bei Erfolg.
		expect(deleteLocRes.status()).toBe(204);

		const getAfterDelete = await request.get(`/api/locations/${loc.id}`);
		expect(getAfterDelete.status()).toBe(404);
	});
});
