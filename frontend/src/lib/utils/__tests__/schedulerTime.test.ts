// TDD RED — Issue #1727 S5e (B): die Scheduler-Zeit folgt der Browser-Zone.
//
// Spec: docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md
//   AC-5  Uhrzeit in der Zone des Browsers + sichtbares Zonenkuerzel
//
// `formatNextRun()` liegt heute als interne Funktion im <script>-Block von
// `frontend/src/routes/account/+page.svelte` (:264-281) und ist von aussen
// NICHT aufrufbar — ein Unit-Test kann sie dort nicht importieren. Sie wandert
// deshalb nach `frontend/src/lib/utils/schedulerTime.ts` (Spec, Implementation
// Details B.5); die Seite importiert sie von dort.
//
// RED-Gruende (gemessen, nicht vermutet):
//   1. `../schedulerTime.ts` existiert noch nicht -> Import schlaegt fehl.
//   2. Nach der reinen Verschiebung waeren die vier `timeZone: 'Europe/Vienna'`-
//      Literale weiterhin drin: beide Zonen lieferten "22:30" statt 22:30/16:30,
//      und ohne `timeZoneName: 'short'` fehlte jedes Kuerzel.
//
// POSITIVKONTROLLE (Spec, AC-5, roter Punkt): der erste Test belegt, dass das
// Umschalten von `process.env.TZ` in DIESEM Prozess ueberhaupt wirkt. Ein
// Testgeruest, in dem TZ folgenlos bleibt, liefert zwei identische Strings —
// und waere auch bei fest verdrahtetem Wien gruen. Der Nachweis liefe ins
// Leere. Darum werden konkrete Uhrzeiten geprueft, nicht nur Ungleichheit.
// Gemessen mit node v22.22.2: 2026-12-24T21:30:00Z ist 22:30 in Wien (MEZ)
// und 16:30 in New York (GMT-5).
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/utils/__tests__/schedulerTime.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { formatNextRun } from '../schedulerTime.ts';

/** Winter-Zeitpunkt: beide Zonen stehen auf Normalzeit, der Abstand ist
 *  stabil 6 Stunden (kein Sommerzeit-Versatz zwischen den Zonen). */
const ISO_FERN = '2026-12-24T21:30:00Z';
const WIEN_STUNDE = 22;
const NEWYORK_STUNDE = 16;

/** Fuehrt `fn` mit gesetzter Prozess-Zeitzone aus und stellt sie danach
 *  wieder her. Node liest TZ bei jedem Date-/Intl-Aufruf neu ein. */
function mitZone<T>(tz: string, fn: () => T): T {
	const vorher = process.env.TZ;
	process.env.TZ = tz;
	try {
		return fn();
	} finally {
		if (vorher === undefined) delete process.env.TZ;
		else process.env.TZ = vorher;
	}
}

describe('formatNextRun — Zone des Browsers statt fest Wien (#1727 S5e, AC-5)', () => {
	test('Positivkontrolle: das Umschalten der Zone wirkt im Testaufbau', () => {
		// Ohne diesen Nachweis waere jeder folgende Test wertlos: bleibt TZ
		// folgenlos, sind zwei Ergebnisse immer gleich — auch bei fest
		// verdrahtetem Europe/Vienna im Pruefling.
		const wien = mitZone('Europe/Vienna', () => new Date(ISO_FERN).getHours());
		const newYork = mitZone('America/New_York', () => new Date(ISO_FERN).getHours());

		assert.equal(
			wien,
			WIEN_STUNDE,
			`Testaufbau: Date sieht in Europe/Vienna Stunde ${wien}, erwartet ${WIEN_STUNDE}`
		);
		assert.equal(
			newYork,
			NEWYORK_STUNDE,
			`Testaufbau: Date sieht in America/New_York Stunde ${newYork}, erwartet ${NEWYORK_STUNDE}`
		);
	});

	test('AC-5: derselbe Zeitpunkt ergibt in zwei Zonen zwei verschiedene Uhrzeiten', () => {
		const wien = mitZone('Europe/Vienna', () => formatNextRun(ISO_FERN));
		const newYork = mitZone('America/New_York', () => formatNextRun(ISO_FERN));

		assert.match(
			wien,
			/\b22:30\b/,
			`In Europe/Vienna formatiert: ${JSON.stringify(wien)} — erwartet die ` +
				`Wiener Uhrzeit 22:30.`
		);
		assert.match(
			newYork,
			/\b16:30\b/,
			`In America/New_York formatiert: ${JSON.stringify(newYork)} — erwartet ` +
				`die New Yorker Uhrzeit 16:30. Steht dort 22:30, ist die Zone noch ` +
				`fest auf Europe/Vienna verdrahtet.`
		);
		assert.notEqual(
			wien,
			newYork,
			'Beide Zonen liefern denselben String — die Anzeige folgt der Browser-Zone nicht.'
		);
	});

	test('AC-5: die Ausgabe traegt in beiden Zonen ein sichtbares Zonenkuerzel', () => {
		// Ohne Kuerzel waere die Zahl nach Wegfall der festen Zone mehrdeutig:
		// "22:30" allein sagt dem Leser nicht, in welcher Zone das gilt.
		const wien = mitZone('Europe/Vienna', () => formatNextRun(ISO_FERN));
		const newYork = mitZone('America/New_York', () => formatNextRun(ISO_FERN));

		assert.match(
			wien,
			/22:30\s+\S+/,
			`In Europe/Vienna: ${JSON.stringify(wien)} — nach der Uhrzeit fehlt das ` +
				`Zonenkuerzel (erwartet z.B. "22:30 MEZ", Option timeZoneName: 'short').`
		);
		assert.match(
			newYork,
			/16:30\s+\S+/,
			`In America/New_York: ${JSON.stringify(newYork)} — nach der Uhrzeit fehlt ` +
				`das Zonenkuerzel (erwartet z.B. "16:30 GMT-5").`
		);
		assert.notEqual(
			wien.replace(/[\d:.,\s]/g, ''),
			newYork.replace(/[\d:.,\s]/g, ''),
			'Beide Ausgaben tragen dasselbe Zonenkuerzel — es ist nicht das der jeweiligen Zone.'
		);
	});

	test('AC-5: auch der nahe Fall ("heute um …") traegt Zone und Kuerzel', () => {
		// Der Regelfall auf der Konto-Seite: `next_run` liegt innerhalb der
		// naechsten Stunde, die Anzeige nimmt den relativen Zweig. Genau dieser
		// Zweig ist auf Staging sichtbar (AC-7) — er darf das Kuerzel nicht
		// verlieren. Bezugspunkt ist die Laufzeit-Uhr, deshalb wird die Struktur
		// geprueft, nicht ein fester Wert.
		const in30Minuten = new Date(Date.now() + 30 * 60_000).toISOString();

		const wien = mitZone('Europe/Vienna', () => formatNextRun(in30Minuten));
		const newYork = mitZone('America/New_York', () => formatNextRun(in30Minuten));

		for (const [zone, wert] of [
			['Europe/Vienna', wien],
			['America/New_York', newYork]
		] as const) {
			assert.match(
				wert,
				/^(heute|morgen) um \d{2}:\d{2}\s+\S+$/,
				`In ${zone}: ${JSON.stringify(wert)} — erwartet "heute um HH:MM <Kuerzel>" ` +
					`(bzw. "morgen um …"). Fehlt der Teil nach der Uhrzeit, fehlt das Zonenkuerzel.`
			);
		}
		assert.notEqual(
			wien,
			newYork,
			`Beide Zonen liefern ${JSON.stringify(wien)} — die Anzeige folgt der Browser-Zone nicht.`
		);
	});

	test('leerer Wert bleibt unveraendert ein Gedankenstrich', () => {
		// Bestandsverhalten (:265) — die Auslagerung darf es nicht veraendern.
		assert.equal(formatNextRun(null), '—');
		assert.equal(formatNextRun(undefined), '—');
		assert.equal(formatNextRun(''), '—');
	});
});
