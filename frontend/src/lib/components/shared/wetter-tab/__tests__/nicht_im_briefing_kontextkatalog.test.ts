// Fix #2944: Orts-Briefing „Nicht im Briefing" bietet nur Metriken des Vergleichs-Katalogs an.
// Spec: docs/specs/modules/fix_2944_orts_nicht_im_briefing.md (AC-1 bis AC-4, AC-6)
//
// Nutzersicht: Im Orts-Briefing (Reiter Wetter) erscheinen im Abschnitt „Nicht im Briefing"
// trip-exklusive Gehzeit-Groessen („Tages-Hoechsttemperatur (Gehzeit)" …) und Nacht-Groessen,
// die fuer Orte nie berechnet werden. Das Angebot muss im Kontext `vergleich` auf den
// Vergleichs-Katalog (`GET /api/compare/metrics`) beschraenkt sein; im Trip bleibt alles.
//
// Kein Mock: zentraler Katalog und Vergleichs-Katalog kommen aus denselben Python-Funktionen,
// die `/api/metrics` und `/api/compare/metrics` im Betrieb beantworten (wetterTabDaten.ts).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/nicht_im_briefing_kontextkatalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { live, liveVergleichsKatalog } from './wetterTabDaten.ts';
import * as modell from '../ampelModell.ts';

/** Die sechs Metriken, die nur der zentrale (Trip-)Katalog kennt (Messung im Kontext-Dokument). */
const TRIP_EXKLUSIV = [
	'temperature_day_high',
	'temperature_day_low',
	'wind_chill_day_high',
	'wind_chill_day_low',
	'temperature_night',
	'wind_chill_night'
];

type Angebot = (context: modell.Kontext, eig: Record<string, modell.MetrikEigenschaften>, auswahl: string[], katalogIds: Set<string>) => string[];

/** Die neue Funktion; fehlt sie (TDD RED), scheitert jeder Test einzeln mit klarer Meldung. */
function briefingAngebot(): Angebot {
	const f = (modell as Record<string, unknown>).briefingAngebot;
	assert.equal(typeof f, 'function', 'TDD RED: ampelModell.briefingAngebot fehlt (Angebot „Nicht im Briefing" je Kontext)');
	return f as Angebot;
}

const eig = () => modell.eigenschaftenAusKatalog(live().metrics);
const katalogIds = () => new Set<string>(liveVergleichsKatalog().metrics.map((e: { metric_id: string }) => e.metric_id));
/** Gewohnte Reihenfolge: zentrale Metriken nach Gruppen (wie bisher in WetterTabInhalt). */
const reihenfolge = (e: Record<string, modell.MetrikEigenschaften>) => modell.zeilenGruppen(Object.keys(e), e).flatMap((g) => g.metriken);

describe('#2944 Vorbedingung: die trip-exklusiven Metriken stehen im zentralen, nicht im Vergleichs-Katalog', () => {
	test('Messung am Bestand stimmt (sonst beweisen die Tests unten nichts)', () => {
		const e = eig();
		const ids = katalogIds();
		for (const id of TRIP_EXKLUSIV) {
			assert.ok(id in e, `${id} fehlt im zentralen Katalog`);
			assert.ok(!ids.has(id), `${id} steht im Vergleichs-Katalog`);
		}
	});
});

describe('#2944 AC-1: Orts-Briefing bietet keine Gehzeit- und Nacht-Groessen an', () => {
	test('Kontext vergleich, leere Auswahl: keine der sechs trip-exklusiven IDs im Angebot', () => {
		const angebot = briefingAngebot()('vergleich', eig(), [], katalogIds());
		const verirrt = angebot.filter((id) => TRIP_EXKLUSIV.includes(id));
		assert.deepEqual(verirrt, [], `Orts-Briefing bietet trip-exklusive Metriken an: ${verirrt.join(', ')}`);
	});

	test('Kontext vergleich mit Auswahl: weiterhin keine trip-exklusive ID', () => {
		const angebot = briefingAngebot()('vergleich', eig(), ['temperature', 'wind'], katalogIds());
		assert.deepEqual(angebot.filter((id) => TRIP_EXKLUSIV.includes(id)), []);
	});
});

describe('#2944 AC-2: Orts-Briefing bietet alle nicht gewaehlten Vergleichs-Metriken an', () => {
	test('leere Auswahl: genau die Vergleichs-Katalog-Metriken, in gewohnter Reihenfolge', () => {
		const e = eig();
		const ids = katalogIds();
		const erwartet = reihenfolge(e).filter((id) => ids.has(id));
		assert.ok(erwartet.length >= 20, `Vergleichs-Katalog unerwartet klein: ${erwartet.length}`);
		assert.deepEqual(briefingAngebot()('vergleich', e, [], ids), erwartet);
	});

	test('mit Auswahl: Vergleichs-Katalog minus Auswahl, vollstaendig', () => {
		const e = eig();
		const ids = katalogIds();
		const auswahl = ['temperature', 'precipitation', 'gust'];
		const erwartet = reihenfolge(e).filter((id) => ids.has(id) && !auswahl.includes(id));
		assert.deepEqual(briefingAngebot()('vergleich', e, auswahl, ids), erwartet);
	});
});

describe('#2944 AC-3: Trip-Briefing bleibt unveraendert', () => {
	test('Kontext route: alle zentralen Metriken minus Auswahl, Gehzeit inklusive', () => {
		const e = eig();
		const auswahl = ['temperature', 'wind'];
		const erwartet = reihenfolge(e).filter((id) => !auswahl.includes(id));
		const angebot = briefingAngebot()('route', e, auswahl, katalogIds());
		assert.deepEqual(angebot, erwartet);
		for (const id of TRIP_EXKLUSIV) assert.ok(angebot.includes(id), `Trip-Briefing bietet ${id} nicht mehr an`);
	});

	test('Kontext route ignoriert den Vergleichs-Katalog (auch leer bleibt alles im Angebot)', () => {
		const e = eig();
		assert.deepEqual(briefingAngebot()('route', e, [], new Set()), reihenfolge(e));
	});
});

describe('#2944 AC-4: bestehende Orts-Auswahl wird nicht angefasst', () => {
	test('Auswahl mit Nicht-Vergleichs-Metrik bleibt identisch, die Metrik erscheint nicht im Angebot', () => {
		const auswahl = ['temperature', 'temperature_day_high'];
		const vorher = [...auswahl];
		const angebot = briefingAngebot()('vergleich', eig(), auswahl, katalogIds());
		assert.deepEqual(auswahl, vorher, 'briefingAngebot hat die Auswahl veraendert');
		assert.ok(!angebot.includes('temperature_day_high'));
		assert.ok(!angebot.includes('temperature'));
	});
});

describe('#2944 AC-6: beide Kontexte ueber dieselbe Funktion', () => {
	test('dieselben Eingaben liefern je Kontext verschiedene Angebote (Kontext wirkt als Daten)', () => {
		const e = eig();
		const ids = katalogIds();
		const f = briefingAngebot();
		const route = f('route', e, [], ids);
		const vergleich = f('vergleich', e, [], ids);
		assert.deepEqual(route.filter((id) => !vergleich.includes(id)).sort(), [...TRIP_EXKLUSIV].sort());
	});
});
