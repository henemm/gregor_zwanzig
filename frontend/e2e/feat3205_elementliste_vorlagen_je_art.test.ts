// Issue #3205 (Epic #2913): Vorlagen je Art im Mockup Fassung 4 (Trip gegen Orts-Vergleich).
// Spec: docs/specs/modules/feat_3205_vorlagen_mockup.md (AC-1, AC-2; Test Plan „Elementlisten-Test“).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3205_elementliste_vorlagen_je_art.test.ts
//
// Geprüft wird die ERZEUGTE Elementliste (docs/context/einstellungen_neu/elementliste.json), nicht der
// Mockup-Quelltext: Sie entsteht deterministisch per scripts/elementliste_aus_mockup.ts aus dem gerenderten
// Mockup und ist per Prüfsumme an den aktuellen Mockup-Stand gebunden. Was hier steht, zeigt das Mockup.
//
// Sollwert „eigene Trip-Vorlage“ kommt aus dem Mockup-Prüfkonto (Kontodaten, kein Katalogtext): der Name,
// den die Trip-Vorlagenauswahl unter der Beschriftung „Eigene“ (Katalog wertebereiche.preset.eigene) führt.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');

type Eintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	i18n_key: string | null;
};

const LISTE: { elemente: Eintrag[] } = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf-8'));

const EIGENE_TRIP_VORLAGE = 'Mallorca Frühling';
const ZUSTAENDE = ['luecken', 'normal'] as const;

/** Einträge der Vorlagenauswahl (Reiter Wetter) eines Kontexts und Zustands, in Dokumentreihenfolge. */
const auswahl = (ctx: string, zustand: string): Eintrag[] =>
	LISTE.elemente
		.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === zustand && e.abschnitt === 'vorlage-auswahl')
		.sort((a, b) => a.ordnung - b.ordnung);

describe('#3205 AC-2: Trip-Vorlagenauswahl führt die eigene Trip-Vorlage weiter', () => {
	for (const zustand of ZUSTAENDE) {
		test(`Trip, Zustand ${zustand}: „${EIGENE_TRIP_VORLAGE}“ steht unter „Eigene“`, () => {
			const liste = auswahl('trip', zustand);
			assert.ok(liste.length > 0, `Trip-Vorlagenauswahl (Zustand ${zustand}) fehlt in der Elementliste`);
			const eigene = liste.findIndex((e) => e.rolle === 'beschriftung' && e.i18n_key === 'wertebereiche.preset.eigene');
			assert.ok(eigene >= 0, `Beschriftung „Eigene“ fehlt in der Trip-Auswahl (Zustand ${zustand})`);
			const name = liste.slice(eigene + 1).find((e) => e.rolle === 'knopf' && e.text_de === EIGENE_TRIP_VORLAGE);
			assert.ok(name, `„${EIGENE_TRIP_VORLAGE}“ fehlt in der Trip-Auswahl (Zustand ${zustand})`);
		});
	}
});

describe('#3205 AC-1: Orte-Vorlagenauswahl zeigt nur Vorlagen der Art Vergleich', () => {
	for (const zustand of ZUSTAENDE) {
		test(`Orte, Zustand ${zustand}: keine eigene Trip-Vorlage „${EIGENE_TRIP_VORLAGE}“`, () => {
			const liste = auswahl('orte', zustand);
			assert.ok(liste.length > 0, `Orte-Vorlagenauswahl (Zustand ${zustand}) fehlt in der Elementliste`);
			// Vorbedingung: die Systemvorlagen stehen weiterhin in der Orte-Auswahl.
			assert.ok(
				liste.some((e) => e.rolle === 'beschriftung' && e.i18n_key === 'wetter.vorlage.systemvorlagen'),
				`Systemvorlagen fehlen in der Orte-Auswahl (Zustand ${zustand})`,
			);
			const treffer = liste.filter((e) => e.text_de.includes(EIGENE_TRIP_VORLAGE));
			assert.deepEqual(
				treffer.map((e) => e.id),
				[],
				`Eigene Trip-Vorlage „${EIGENE_TRIP_VORLAGE}“ erscheint in der Orte-Vorlagenauswahl (Zustand ${zustand}); Mockup-Picker muss je Art filtern`,
			);
		});
	}
});
