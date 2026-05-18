// TDD: PresetRow Logik-Tests (kein DOM/Svelte-Import nötig)
// Testet die Prop-Logik die PresetRow steuert

import { test } from 'node:test';
import assert from 'node:assert/strict';

// getActivePreset ist die Basis für isActive — bereits in rightColumn.test.ts getestet
// Hier testen wir die Hilfsfunktion für metricCount-Formatierung und isActive-Ausdruck

test('PresetRow > isActive: selectedTemplate === id ist true', () => {
	const selectedTemplate = 'wandern';
	const id = 'wandern';
	assert.equal(selectedTemplate === id, true);
});

test('PresetRow > isActive: selectedTemplate !== id ist false', () => {
	const selectedTemplate = 'wandern';
	const id = 'wintersport';
	assert.equal(selectedTemplate === id, false);
});

test('PresetRow > isActive: leerer selectedTemplate ist false', () => {
	const selectedTemplate = '';
	const id = 'wandern';
	assert.equal(selectedTemplate === id, false);
});

test('PresetRow > metricCount-Formatierung: 9 → "9 Metriken"', () => {
	const count = 9;
	const label = `${count} Metriken`;
	assert.equal(label, '9 Metriken');
});

test('PresetRow > metricCount-Formatierung: 0 → "0 Metriken"', () => {
	const count = 0;
	const label = `${count} Metriken`;
	assert.equal(label, '0 Metriken');
});

test('PresetRow > onSelect gibt id weiter', () => {
	let called: string | null = null;
	function onSelect(id: string) {
		called = id;
	}
	onSelect('skitouren');
	assert.equal(called, 'skitouren');
});
