// TDD RED — Issue #2248 (Scheibe 3 von #2199): einmaliges, geraeteuebergreifend
// abweisbares Passkey-Angebot.
// Spec: docs/specs/modules/passkey_angebot_banner.md — AC-7 und AC-8.
//
// Geprueft wird das echte Modul ./passkeyAngebot.ts — relativ zur eigenen
// Testdatei aufgeloest, nie ueber einen festen Hauptrepo-Pfad (sonst faelscht
// ein Worktree-Lauf sein Gruen aus dem Hauptcheckout herbei). Eine im Test
// nachgebaute Kopie der Entscheidungstabelle pruefte nur sich selbst.
//
// RED ist es, weil ./passkeyAngebot.ts heute nicht existiert — der Lauf
// scheitert schon beim Auflösen des Imports.
//
// Ausfuehrung:
//   cd frontend && npm test -- src/lib/passkeyAngebot.test.ts
//
// ---------------------------------------------------------------------
// Vertrag, den die Implementierung erfuellen muss (RED legt ihn fest):
//
//   passkeyAngebotFaellig({ marker, hasPasskey, dismissed, webauthnFaehig }): boolean
//     Vier BOOLEAN-Eingaben, alle von aussen. `marker` ist "der Anmelde-Marker
//     steht in der Adresse" (true/false), nicht der Rohwert des
//     Query-Parameters. Die Funktion liest nichts selbst — nur so ist sie
//     ampeltauglich (Spec, Analyse-Entscheidung B).
//
//   mitAngebotMarker(pfad: string): string
//     Haengt den Anmelde-Marker als eigenstaendigen Query-Parameter an einen
//     relativen Pfad, der bereits eine Query tragen kann.
//
// Der NAME des Markers ist absichtlich nirgends festgeschrieben: er muss nur
// auf beiden Seiten derselbe sein, und diese Tests pruefen genau das
// (derselbe Schluessel in beiden Zweigen) statt eine Schreibweise zu zementieren.
//
// AC-1 bis AC-5 stehen NICHT hier: die Sichtbarkeit haengt an
// isWebAuthnSupported() (nur im Browser). Eine serverseitige Zusicherung
// "Banner fehlt" stellt sich im SSR von selbst ein und bewacht nichts
// (Kontext, Risiko 1) — sie gehoert in frontend/e2e/passkey-angebot.spec.ts.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { passkeyAngebotFaellig, mitAngebotMarker } from './passkeyAngebot.ts';

/** Die Lage, in der das Angebot faellig ist — Ausgangspunkt jedes Ausschlussfalls. */
const guenstig = {
	marker: true,
	hasPasskey: false,
	dismissed: false,
	webauthnFaehig: true
};

// ── AC-7: Entscheidungstabelle ────────────────────────────────────────────────

// Der eine Erfolgsfall. Ohne ihn bestuenden die vier Ausschlussfaelle unten
// auch dann, wenn die Funktion pauschal `false` lieferte.
test('AC-7: Marker gesetzt, kein Passkey, nicht abgewiesen, Geraet faehig → Angebot zeigen', () => {
	assert.equal(passkeyAngebotFaellig({ ...guenstig }), true);
});

// Die vier Ausschlussfaelle EINZELN, bei sonst guenstiger Lage. So ist
// nachgewiesen, dass jeder Faktor allein traegt — eine Tabelle, die nur
// Kombinationen prueft, laesst offen, welcher Faktor gerade gewirkt hat.
test('AC-7: ohne Anmelde-Marker kein Angebot (sonst guenstige Lage)', () => {
	assert.equal(
		passkeyAngebotFaellig({ ...guenstig, marker: false }),
		false,
		'ohne Marker wuerde das Angebot bei jeder Navigation erscheinen, nicht einmalig nach dem Login'
	);
});

test('AC-7: mit hinterlegtem Passkey kein Angebot (sonst guenstige Lage)', () => {
	assert.equal(
		passkeyAngebotFaellig({ ...guenstig, hasPasskey: true }),
		false,
		'wer schon einen Passkey hat, soll das Angebot nie sehen'
	);
});

test('AC-7: nach Abweisung kein Angebot (sonst guenstige Lage)', () => {
	assert.equal(
		passkeyAngebotFaellig({ ...guenstig, dismissed: true }),
		false,
		'die serverseitig gemerkte Abweisung muss das Angebot auf JEDEM Geraet unterdruecken'
	);
});

test('AC-7: ohne WebAuthn-Faehigkeit kein Angebot (sonst guenstige Lage)', () => {
	assert.equal(
		passkeyAngebotFaellig({ ...guenstig, webauthnFaehig: false }),
		false,
		'ein Angebot, das das Geraet nicht einloesen kann, ist eine Sackgasse'
	);
});

// Vollstaendige Tabelle: von den 16 Kombinationen darf GENAU EINE `true`
// liefern. Faengt eine Implementierung, die zwei Faktoren mit `||` statt `&&`
// verknuepft und in den Einzelfaellen oben trotzdem bestehen koennte.
test('AC-7: von allen 16 Kombinationen liefert genau eine "Angebot zeigen"', () => {
	const zeigen: string[] = [];
	for (const marker of [false, true]) {
		for (const hasPasskey of [false, true]) {
			for (const dismissed of [false, true]) {
				for (const webauthnFaehig of [false, true]) {
					if (passkeyAngebotFaellig({ marker, hasPasskey, dismissed, webauthnFaehig })) {
						zeigen.push(`marker=${marker} hasPasskey=${hasPasskey} dismissed=${dismissed} webauthnFaehig=${webauthnFaehig}`);
					}
				}
			}
		}
	}
	assert.deepEqual(zeigen, ['marker=true hasPasskey=false dismissed=false webauthnFaehig=true'], 'erwartet genau eine zeigende Kombination');
});

// ── AC-8: Marker an die Weiterleitungs-Adresse haengen ───────────────────────

const BASIS = 'https://x.invalid';

/** Zerlegt das Ergebnis so, wie der Browser es tun wuerde. */
function zerlege(ergebnis: string): URL {
	// Wirft bei kaputter Adresse — genau das ist Teil der Zusicherung.
	return new URL(ergebnis, BASIS);
}

test('AC-8: Pfad ohne Query bekommt den Marker als eigenstaendigen Parameter', () => {
	const ergebnis = mitAngebotMarker('/');
	const url = zerlege(ergebnis);

	assert.equal(url.pathname, '/', `Pfad veraendert: ${ergebnis}`);
	const parameter = [...url.searchParams.keys()];
	assert.equal(
		parameter.length,
		1,
		`erwartet genau einen Query-Parameter (den Marker), bekommen ${JSON.stringify(parameter)} aus ${ergebnis}`
	);
	assert.notEqual(url.searchParams.get(parameter[0]), null, `Marker hat keinen Wert: ${ergebnis}`);
});

test('AC-8: Pfad mit bestehender Query behaelt sie und bekommt den Marker daneben', () => {
	const ergebnis = mitAngebotMarker('/trips?filter=aktiv');
	const url = zerlege(ergebnis);

	assert.equal(url.pathname, '/trips', `Pfad veraendert: ${ergebnis}`);

	// Der eigentliche Fang: wird der Marker mit einem zweiten "?" statt mit
	// "&" angehaengt ("/trips?filter=aktiv?marker=1"), liest der Browser
	// filter="aktiv?marker=1" — die bestehende Angabe ist dann verfaelscht.
	assert.equal(
		url.searchParams.get('filter'),
		'aktiv',
		`bestehender Parameter filter wurde verfaelscht oder verschluckt: ${ergebnis}`
	);

	const parameter = [...url.searchParams.keys()];
	assert.equal(
		parameter.length,
		2,
		`erwartet zwei Query-Parameter (filter + Marker), bekommen ${JSON.stringify(parameter)} aus ${ergebnis}`
	);

	// Beide Zweige muessen DENSELBEN Schluessel anhaengen — sonst sucht das
	// Layout nach einem Marker, den der eine Zweig nie schreibt.
	const markerOhneQuery = [...zerlege(mitAngebotMarker('/')).searchParams.keys()][0];
	const markerMitQuery = parameter.find((p) => p !== 'filter');
	assert.equal(
		markerMitQuery,
		markerOhneQuery,
		'die beiden Zweige haengen unterschiedliche Marker-Schluessel an — das Layout kann nur einen lesen'
	);
});
