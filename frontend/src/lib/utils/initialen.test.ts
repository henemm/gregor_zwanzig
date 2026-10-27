import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialen } from './initialen.ts';

test('Anzeigename mit zwei Wörtern liefert beide Anfangsbuchstaben', () => {
	assert.equal(initialen('Henning Emmrich'), 'HE');
});

test('Ein-Wort-Name liefert die ersten zwei Buchstaben, groß', () => {
	assert.equal(initialen('Henning'), 'HE');
	assert.equal(initialen('hem', null), 'HE');
});

test('Ohne Anzeigename fällt der Kreis auf die Login-Kennung zurück', () => {
	assert.equal(initialen('', 'admin'), 'AD');
	assert.equal(initialen(null, 'max.mustermann'), 'MM');
});

test('Ganz ohne Namen zeigt der Kreis ein Fragezeichen statt leer zu bleiben', () => {
	assert.equal(initialen(undefined, undefined), '?');
	assert.equal(initialen('   ', ''), '?');
});
