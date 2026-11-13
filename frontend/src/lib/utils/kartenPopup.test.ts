// Issue #2961 (FE1) — Wegpunktnamen erscheinen in der Karten-Sprechblase als Text.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-1)
// Der Browser-Nachweis (echtes Leaflet, echtes DOM) steht in
// e2e/karte-wegpunktname-als-text.spec.ts; hier wird der Baustein selbst
// geprueft: er liefert einen Knoten (keine Zeichenkette, die Leaflet als HTML
// einsetzen wuerde) und setzt den Namen ausschliesslich als Text.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/utils/kartenPopup.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { popupKnoten, popupText, type KnotenFabrik } from './kartenPopup.ts';

/** Minimales Element: haelt fest, ob jemals HTML eingesetzt wurde. */
class Element {
	tagName: string;
	textContent = '';
	htmlGesetzt = false;
	constructor(tag: string) {
		this.tagName = tag.toUpperCase();
	}
	set innerHTML(_wert: string) {
		this.htmlGesetzt = true;
	}
	set outerHTML(_wert: string) {
		this.htmlGesetzt = true;
	}
}

const dokument = {
	createElement: (tag: string) => new Element(tag)
} as unknown as KnotenFabrik;

const AUSZEICHNUNG = '<img src=x onerror="globalThis.__gz=1">';

test('AC-1: ein Name mit Auszeichnung wird woertlich als Text uebernommen', () => {
	const knoten = popupKnoten(dokument, 3, AUSZEICHNUNG) as unknown as Element;
	assert.equal(typeof knoten, 'object', 'Leaflet bekaeme eine Zeichenkette und setzte sie als HTML ein');
	assert.equal(knoten.textContent, `3. ${AUSZEICHNUNG}`);
	assert.equal(knoten.htmlGesetzt, false, 'der Name wurde als HTML eingesetzt');
});

test('AC-1: fehlender Name ergibt nur die Nummer', () => {
	assert.equal(popupText(1, undefined), '1. ');
	assert.equal(popupText(2, null), '2. ');
	assert.equal((popupKnoten(dokument, 1, null) as unknown as Element).textContent, '1. ');
});
