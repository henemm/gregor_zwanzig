/**
 * TDD RED — Issue #452: Smart-Import Vervollständigung (Step2Orte)
 *
 * Spec: docs/specs/modules/issue_452_smart_import_step2.md
 *
 * Diese Tests prüfen die Quelldatei Step2Orte.svelte auf das Vorhandensein
 * der neu spezifizierten Elemente. Im RED-Zustand müssen sie FEHLSCHLAGEN,
 * weil die Implementierung noch nicht existiert.
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

const COMPONENT_PATH = join(
	import.meta.dirname,
	'../steps/Step2Orte.svelte'
);

const source = readFileSync(COMPONENT_PATH, 'utf-8');

describe('Issue #452 — Step2Orte Smart-Import Vervollständigung', () => {
	// AC-4: Fallback-Felder bei unbekanntem Format
	it('AC-4: compare-step2-fallback-lat testid vorhanden', () => {
		assert.ok(
			source.includes('compare-step2-fallback-lat'),
			'FEHLT: data-testid="compare-step2-fallback-lat" — AC-4 nicht implementiert'
		);
	});

	it('AC-4: compare-step2-fallback-lon testid vorhanden', () => {
		assert.ok(
			source.includes('compare-step2-fallback-lon'),
			'FEHLT: data-testid="compare-step2-fallback-lon" — AC-4 nicht implementiert'
		);
	});

	it('AC-4: compare-step2-fallback-add-btn testid vorhanden', () => {
		assert.ok(
			source.includes('compare-step2-fallback-add-btn'),
			'FEHLT: data-testid="compare-step2-fallback-add-btn" — AC-4 nicht implementiert'
		);
	});

	it('AC-4: addLocationFromFallback Funktion vorhanden', () => {
		assert.ok(
			source.includes('addLocationFromFallback'),
			'FEHLT: Funktion addLocationFromFallback — AC-4 nicht implementiert'
		);
	});

	it('AC-4: fallbackLat State vorhanden', () => {
		assert.ok(
			source.includes('fallbackLat'),
			'FEHLT: $state fallbackLat — AC-4 nicht implementiert'
		);
	});

	it('AC-4: fallbackLon State vorhanden', () => {
		assert.ok(
			source.includes('fallbackLon'),
			'FEHLT: $state fallbackLon — AC-4 nicht implementiert'
		);
	});

	// AC-5: Preview zeigt Höhe und Zeitzone
	it('AC-5: Höhe-Label im Preview sichtbar (elevation_m-Conditional)', () => {
		assert.ok(
			source.includes('elevation_m !== undefined'),
			'FEHLT: {#if preview.elevation_m !== undefined} Block — AC-5 Höhe nicht implementiert'
		);
	});

	it('AC-5: Höhe-Text-Label vorhanden', () => {
		assert.ok(
			source.includes('Höhe:') || source.includes('Höhe'),
			'FEHLT: "Höhe:" Text im Preview-Block — AC-5 nicht implementiert'
		);
	});

	it('AC-5: Zeitzone im Preview-Template (nicht nur API-Call)', () => {
		// preview.timezone muss im Template (nicht nur im addLocation-API-Call) vorkommen
		// Prüfung: Muss NACH dem {#if preview}-Template-Block erscheinen
		const templateSection = source.split('{#if preview}')[1] ?? '';
		assert.ok(
			templateSection.includes('preview.timezone') || templateSection.includes('timezone'),
			'FEHLT: preview.timezone im Preview-Template — AC-5 Zeitzone nicht implementiert'
		);
	});
});
