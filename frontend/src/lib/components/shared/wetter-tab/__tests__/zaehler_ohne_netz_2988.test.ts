// #2988 AC-1 (S1, wiederholt in S3): der Zaehler stimmt sofort nach jeder Eingabe, ohne Netzaufruf.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Pruefstand: reiter2988.ts (echter Reiter).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { reiter2988 } from './reiter2988.ts';

for (const context of ['route', 'vergleich'] as const) {
	describe(`AC-1 (#2988, ${context}): Zaehler sofort und ohne Netz`, () => {
		test('jede_eingabe_aendert_die_zahl_sofort_ohne_aufruf', async () => {
			const r = await reiter2988(context, { template: 'wandern' });
			const beimLaden = r.aufrufe.length;
			assert.equal(r.zahl(), 0);
			assert.equal(r.geplant(), 0, 'Laden plant ein Speichern');

			// Waehrend des Tippens (Entwurf offen, noch nicht „Fertig“).
			r.tippen('gust', 'upper', 'yellow', 41);
			assert.equal(r.zahl(), 1, 'Grenze während des Tippens');
			assert.equal(r.u.fertig(), true);
			assert.equal(r.zahl(), 1, 'Grenze nach Fertig');

			const stufe = r.u.stand.ampel.metrics.wind.alarm_ab === 'red' ? 'never' : 'red';
			r.u.aendern(r.u.Z.mitAlarmAb(r.u.stand, 'wind', stufe));
			assert.equal(r.zahl(), 2, 'Alarm ab');
			r.u.entfernen('precipitation');
			assert.equal(r.zahl(), 3, 'Metrik entfernt');
			r.u.hinzufuegen('dewpoint');
			assert.equal(r.zahl(), 4, 'Metrik hinzugefügt');

			const farbe = r.u.stand.ampel.thunder.mittel === 'red' ? 'orange' : 'red';
			r.u.grenzenUmschalten('thunder');
			r.u.gewitterWahl('mittel', farbe);
			assert.equal(r.zahl(), 5, 'Gewitterfarbe');
			assert.equal(r.u.fertig(), true);
			assert.equal(r.zahl(), 5);

			r.zuruecksetzen();
			assert.equal(r.zahl(), 0, 'Zurücksetzen');
			r.uebernehmen('skitouren');
			assert.equal(r.u.stand.vorlageId, 'skitouren');
			assert.equal(r.zahl(), 0, 'Vorlage übernommen');

			assert.deepEqual(r.aufrufe.slice(beimLaden), [], 'Netzaufruf während der Eingabe');
			assert.ok(r.geplant() > 0, 'Messaufbau: Eingaben lösen kein Speichern aus');
		});
		test('zuruecknehmen_zaehlt_nicht', async () => {
			const r = await reiter2988(context, { template: 'wandern' });
			const vorher = r.u.stand.ampel.metrics.gust.upper.yellow;
			r.grenze('gust', 'upper', 'yellow', vorher + 1);
			assert.equal(r.zahl(), 1);
			r.grenze('gust', 'upper', 'yellow', vorher);
			assert.equal(r.zahl(), 0);
			r.u.entfernen('gust');
			assert.equal(r.zahl(), 1);
			r.u.hinzufuegen('gust');
			assert.equal(r.zahl(), 0);
		});
	});
}
