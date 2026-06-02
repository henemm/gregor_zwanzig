// TDD RED — Issue #514: Compare-Vorschau-Tab: Echte E-Mail-Vorschau
//
// Spec: docs/specs/modules/issue_514_compare_vorschau_tab.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Implementation):
//   AC-1: FAIL — kein $effect mit Preview-Endpoint-Aufruf
//   AC-2: FAIL — kein iframe srcdoc auf warmem Grau-Hintergrund (#e9e6dc)
//   AC-3: FAIL — kein Design-Heading "Vorschau · Verifikation"
//   AC-4: FAIL — kein Segmented-Kanal-Umschalter mit "SMS / Signal"
//   AC-5: FAIL — kein compare-send-success testid
//   AC-6: FAIL — kein compare-preview-error testid
//   AC-7: FAIL — kein compare-preview-sms-hint testid
//   AC-8: FAIL — Placeholder "CompareEmail implementiert ist" noch vorhanden
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_514_compare_vorschau_tab.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dir = dirname(__filename);
const TABS_PATH = join(__dir, '..', 'CompareTabs.svelte');

function getSrc(): string {
	return readFileSync(TABS_PATH, 'utf-8');
}

// ── AC-1: Auto-Load via $effect ────────────────────────────────────────────────
describe('AC-1: Vorschau-Tab lädt automatisch via $effect', () => {
	test('CompareTabs.svelte existiert', () => {
		assert.ok(existsSync(TABS_PATH), 'CompareTabs.svelte nicht gefunden');
	});

	test("Source enthält $effect für den Vorschau-Tab", () => {
		assert.ok(
			getSrc().includes('$effect'),
			"CompareTabs.svelte enthält kein $effect — Auto-Load fehlt"
		);
	});

	test("Source enthält Preview-Endpoint '/api/_validator/compare-email-preview'", () => {
		assert.ok(
			getSrc().includes('/api/_validator/compare-email-preview'),
			"CompareTabs.svelte enthält nicht den Preview-Endpoint — API-Anbindung fehlt"
		);
	});

	test("data-testid='compare-preview-loading' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-preview-loading'),
			"CompareTabs.svelte enthält nicht data-testid='compare-preview-loading' — Lade-Zustand fehlt"
		);
	});
});

// ── AC-2: iframe auf warmem Grau-Hintergrund ───────────────────────────────────
describe('AC-2: iframe srcdoc zentriert auf warmem Grau (#e9e6dc)', () => {
	test("Source enthält iframe mit srcdoc", () => {
		assert.ok(
			getSrc().includes('srcdoc'),
			"CompareTabs.svelte enthält kein srcdoc — iframe-Rendering fehlt"
		);
	});

	test("Source enthält sandbox='allow-same-origin'", () => {
		assert.ok(
			getSrc().includes('sandbox'),
			"CompareTabs.svelte enthält kein sandbox-Attribut — sicheres iframe fehlt"
		);
	});

	test("data-testid='compare-preview-iframe' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-preview-iframe'),
			"CompareTabs.svelte enthält nicht data-testid='compare-preview-iframe'"
		);
	});

	test("Warmer Grau-Hintergrund '#e9e6dc' vorhanden (Design-Referenz HubPreview)", () => {
		assert.ok(
			getSrc().includes('#e9e6dc'),
			"CompareTabs.svelte enthält nicht '#e9e6dc' — Design-Hintergrundfarbe fehlt"
		);
	});
});

// ── AC-3: Design-Überschrift ────────────────────────────────────────────────────
describe('AC-3: Design-Heading nach screen-trip-detail.jsx HubPreview', () => {
	test("Eyebrow 'Vorschau · Verifikation' vorhanden", () => {
		assert.ok(
			getSrc().includes('Vorschau · Verifikation'),
			"CompareTabs.svelte enthält nicht 'Vorschau · Verifikation' — Design-Eyebrow fehlt"
		);
	});

	test("H2 'So sieht dein nächstes Briefing aus' vorhanden", () => {
		assert.ok(
			getSrc().includes('So sieht dein nächstes Briefing aus'),
			"CompareTabs.svelte enthält nicht den H2-Titel — Design-Überschrift fehlt"
		);
	});

	test("Disclaimer 'Beispielwerte' vorhanden", () => {
		assert.ok(
			getSrc().includes('Beispielwerte'),
			"CompareTabs.svelte enthält nicht 'Beispielwerte' — Disclaimer fehlt"
		);
	});
});

// ── AC-4: Kanal-Umschalter ─────────────────────────────────────────────────────
describe('AC-4: Segmented Kanal-Umschalter Email | SMS / Signal', () => {
	test("Source enthält 'SMS / Signal'", () => {
		assert.ok(
			getSrc().includes('SMS / Signal'),
			"CompareTabs.svelte enthält nicht 'SMS / Signal' — Kanal-Umschalter fehlt"
		);
	});

	test("Source enthält previewChannel-State", () => {
		assert.ok(
			getSrc().includes('previewChannel'),
			"CompareTabs.svelte enthält nicht 'previewChannel' — Kanal-State fehlt"
		);
	});
});

// ── AC-5: Test-Briefing senden ─────────────────────────────────────────────────
describe('AC-5: Test-Briefing senden — Erfolgs-Feedback', () => {
	test("Send-Endpoint '/api/compare/presets/' + '/send' referenziert", () => {
		assert.ok(
			getSrc().includes('/api/compare/presets/') && getSrc().includes('/send'),
			"CompareTabs.svelte enthält nicht den Send-Endpoint — Versand-Logik fehlt"
		);
	});

	test("data-testid='compare-send-btn' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-send-btn'),
			"CompareTabs.svelte enthält nicht data-testid='compare-send-btn'"
		);
	});

	test("data-testid='compare-send-success' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-send-success'),
			"CompareTabs.svelte enthält nicht data-testid='compare-send-success' — Erfolgs-Feedback fehlt"
		);
	});

	test("Erfolgstext 'Briefing wurde zur Zustellung vorgemerkt' vorhanden", () => {
		assert.ok(
			getSrc().includes('Briefing wurde zur Zustellung vorgemerkt'),
			"CompareTabs.svelte enthält nicht den Erfolgstext — Nutzer-Feedback fehlt"
		);
	});
});

// ── AC-6: Fehler-Handling ──────────────────────────────────────────────────────
describe('AC-6: Fehler-Handling bei API-Fehler', () => {
	test("data-testid='compare-preview-error' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-preview-error'),
			"CompareTabs.svelte enthält nicht data-testid='compare-preview-error' — Fehler-Handling fehlt"
		);
	});

	test("data-testid='compare-send-error' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-send-error'),
			"CompareTabs.svelte enthält nicht data-testid='compare-send-error'"
		);
	});
});

// ── AC-7: SMS-Hinweis ──────────────────────────────────────────────────────────
describe('AC-7: SMS/Signal-Kanal zeigt Hinweis', () => {
	test("data-testid='compare-preview-sms-hint' vorhanden", () => {
		assert.ok(
			getSrc().includes('compare-preview-sms-hint'),
			"CompareTabs.svelte enthält nicht data-testid='compare-preview-sms-hint' — SMS-Hinweis fehlt"
		);
	});

	test("Hinweis-Text 'SMS/Signal-Vorschau ist noch nicht verfügbar' vorhanden", () => {
		assert.ok(
			getSrc().includes('SMS/Signal-Vorschau ist noch nicht verf'),
			"CompareTabs.svelte enthält nicht den SMS-Hinweis-Text"
		);
	});
});

// ── AC-8: Kein Placeholder mehr ────────────────────────────────────────────────
describe('AC-8: Alter Placeholder entfernt', () => {
	test("Placeholder 'CompareEmail implementiert ist' ist NICHT mehr vorhanden", () => {
		assert.ok(
			!getSrc().includes('CompareEmail implementiert ist'),
			"CompareTabs.svelte enthält noch den alten Placeholder — muss entfernt werden"
		);
	});

	test("Import von '$lib/api.js' vorhanden", () => {
		assert.ok(
			getSrc().includes("'$lib/api.js'") || getSrc().includes('"$lib/api.js"'),
			"CompareTabs.svelte importiert nicht '$lib/api.js' — API-Import fehlt"
		);
	});
});
