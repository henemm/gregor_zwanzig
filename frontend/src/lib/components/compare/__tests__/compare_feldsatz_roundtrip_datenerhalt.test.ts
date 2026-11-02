// TDD RED (Regressionswächter) — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-19 (Datenerhalt #102)
//
// Round-Trip: ein Ortsvergleich, in dem JEDES Feld belegt ist (`vollerVergleich`), wird im Hub
// geöffnet; der Hub hält seinen Feldsatz lokal (`compareFeldsatzStandard()`, hydriert aus dem
// Preset wie CompareTabs:408–419). Der Nutzer ändert EINEN Wert im Versand-Abschnitt über den
// Rückruf des Hub-Adapters (`versandPropsAus(feldsatz).onMorningTimeChange`), gespeichert wird über
// den UNVERÄNDERTEN Speicherweg (`erstelleVersandVergleichSpeicherung`, Hub-Queue, echtes `$lib/api`).
// Erwartung: der gespeicherte Datensatz trägt die Änderung, ALLE übrigen Felder sind unverändert —
// es entsteht kein weiterer Schreibweg und kein Voll-Replace (Read-Modify-Write mit Merge).
//
// Netzgrenze: `createGoMergeServer` (Merge exakt nach Go-Regel, goMergeServerPruefstand.ts) —
// aufgezeichnete Server-Semantik, kein Mock der eigenen Annahme.
//
// Warum heute rot: `compareFeldsatzStandard` fehlt (VERTRAG FEHLT). Fachlich ist das ein
// Regressionswächter: der Speicherweg selbst ist heute schon datenerhaltend und muss es nach dem
// Umbau auf den lokalen Feldsatz bleiben.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../compareHubPersistenz.ts';
import { versandPropsAus } from '../versandPropsAus.ts';
import { alarmePropsAus } from '../alarmePropsAus.ts';
import {
	erstelleVersandVergleichSpeicherung,
	hydrateVersandFieldsFromPreset
} from '../../shared/versandVergleichSpeicherung.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../shared/__tests__/goMergeServerPruefstand.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import { neuerFeldsatz } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';

const ID = 'c-2727-rt';
let server: GoMergeServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
});
afterEach(() => server.restore());

/** Hub-Nachbau: lokaler Feldsatz + Versand-Hydration + unveränderter Versand-Speicherweg. */
function hubMitFeldsatz() {
	let currentPreset = vollerVergleich(ID) as unknown as ComparePreset;
	const feldsatz = neuerFeldsatz();
	Object.assign(feldsatz, hydrateVersandFieldsFromPreset(currentPreset));
	const ctl = createController(ID);
	const queue = createPutQueue();
	const speicherung = erstelleVersandVergleichSpeicherung({
		client: api,
		zustand: feldsatz as never,
		preset: () => currentPreset,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			currentPreset = p;
		},
		saveController: ctl
	});
	return { feldsatz, ctl, speicherung };
}

describe('AC-19: einen Reiter ändern — alle übrigen Felder des Presets bleiben erhalten', () => {
	test('Morgen-Uhrzeit im Versand ändern ⇒ nur morning_time ändert sich, der Rest ist bitgleich', async () => {
		const vorher = server.stand(ID);
		const { feldsatz, ctl, speicherung } = hubMitFeldsatz();
		versandPropsAus(feldsatz).onMorningTimeChange('07:15');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(server.putRuempfe().length, 1, 'genau ein PUT über den Versand-Speicherweg erwartet');
		const nachher = server.stand(ID);
		assert.equal(nachher.morning_time, '07:15:00', 'die Änderung kam nicht an');
		const verloren = Object.keys(vorher).filter(
			(k) => k !== 'morning_time' && JSON.stringify(nachher[k]) !== JSON.stringify(vorher[k])
		);
		assert.deepEqual(verloren, [], `Felder verändert/verloren: ${verloren.map((k) => `${k}: ${JSON.stringify(vorher[k])} → ${JSON.stringify(nachher[k])}`).join(' | ')}`);
	});

	test('der PUT-Körper ist ein Teilfeld-Patch, kein Voll-Replace (keine fremden Reiter im Körper)', async () => {
		const { feldsatz, ctl, speicherung } = hubMitFeldsatz();
		versandPropsAus(feldsatz).onMorningTimeChange('07:15');
		speicherung.aenderungMelden();
		await ctl.flush();
		const koerper = server.putRuempfe()[0] ?? {};
		for (const fremd of ['corridors', 'location_ids', 'name', 'display_config']) {
			assert.ok(!(fremd in koerper), `Versand-PUT trägt das Fremdfeld ${fremd}`);
		}
	});

	test('der geteilte Cooldown (Versand ↔ Alarme) reist mit dem hydrierten Wert, nicht mit einem Platzhalter', async () => {
		const { feldsatz, ctl, speicherung } = hubMitFeldsatz();
		assert.equal(alarmePropsAus(feldsatz).cooldownMinutes, 45, 'Vorbedingung: Cooldown aus dem Preset hydriert');
		versandPropsAus(feldsatz).onMorningTimeChange('07:15');
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(server.stand(ID).alert_cooldown_minutes, 45, 'Cooldown wurde beim Versand-PUT verfälscht');
	});
});
