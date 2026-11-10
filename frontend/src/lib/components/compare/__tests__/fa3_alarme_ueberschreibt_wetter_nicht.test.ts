// Fix-Loop 2 Issue #2794 S3a Teil-PR 3, Adversary-Finding F-A3 (HIGH, AC-20/AC-21/AC-38):
// Im Vergleichs-Hub besitzt der Alarme-Speicherer (Reiter Zustellung, bis Teil-PR 4) weiterhin
// `official_warnings` und `radar_alert_enabled` und sendet sie bei JEDER Alarm-Aenderung aus
// `wizardState` mit. Speichert der Reiter Wetter Radar oder Warnungen, muss `wizardState` diese
// Felder aus der Serverantwort uebernehmen — sonst schreibt die naechste Cooldown-Aenderung den
// alten Stand still zurueck (Last-Writer-Wins ohne 412).
//
// Gemessen am Hub-Weg (Muster f003): echter Go-Merge-Pruefserver, echte Hub-Schlange, echter
// Controller, echtes `api`; der Reiter Wetter speichert ueber `SPEICHERER.vergleich`, die
// Antwort geht an die ECHTE `uebernehmeWetterAntwort` aus CompareTabs.svelte
// (Instanz-Skript, svelteInstanzPruefstand.ts), der Alarme-Speicherer ist der echte
// `erstelleAlarmeVergleichSpeicherung` auf demselben `wizardState` und derselben Basis.
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/fa3_alarme_ueberschreibt_wetter_nicht.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../../shared/alarmeVergleichSpeicherung.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../shared/__tests__/goMergeServerPruefstand.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../../shared/wetter-tab/ampelModell.ts';
import { standAusAbo, type AboSicht, type WetterStand } from '../../shared/wetter-tab/wetterZustand.ts';
import { SPEICHERER } from '../../shared/wetter-tab/wetterTabSpeicherung.ts';

const HUB = join(dirname(fileURLToPath(import.meta.url)), '..', 'CompareTabs.svelte');
const ID = 'cp-2794-fa3';
const PFAD = `/api/compare/presets/${ID}`;
const vorlagen = vorlagenAusTemplates(live().templates);

/** Radar aus, Warnungen an — der Reiter Wetter dreht beides um. */
function abo(): Record<string, unknown> {
	const v = vollerVergleich(ID);
	v.radar_alert_enabled = false;
	v.official_alerts_enabled = true;
	v.official_warnings = { enabled: true, sources: ['meteoalarm'] };
	(v.display_config as Record<string, unknown>).active_metrics = [{ metric_id: 'wind', aggregation: 'max' }];
	return v;
}

let server: GoMergeServer;
beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: abo() });
	server.install();
	await api.get(PFAD);
});
afterEach(() => server.restore());

async function hub() {
	const ctl = createController(ID);
	const queue = createPutQueue();
	const wizardState: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(wizardState as never, abo() as unknown as ComparePreset, []);
	const { u } = await umgebungFuer(HUB, {
		preset: abo(),
		locations: [],
		saveController: ctl,
		wizardState,
		api,
		onScheduleChange: undefined,
		alarmeHydrated: true // Zustellung wurde schon geoeffnet
	});
	assert.equal(typeof u.uebernehmeWetterAntwort, 'function', 'Messaufbau: uebernehmeWetterAntwort nicht herleitbar');
	const alarme = erstelleAlarmeVergleichSpeicherung({
		client: api,
		zustand: wizardState,
		preset: () => u.currentPreset as ComparePreset,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			u.currentPreset = p;
		},
		saveController: ctl
	} as never);
	let stand: WetterStand = standAusAbo('vergleich', abo() as AboSicht, vorlagen);
	const wetter = SPEICHERER.vergleich({
		client: api,
		stand: () => stand,
		vorlagen: () => vorlagen,
		abo: () => u.currentPreset as AboSicht,
		saveController: ctl,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		uebernehmen: (a) => (u.uebernehmeWetterAntwort as (p: unknown) => void)(a)
	});
	return {
		ctl,
		wizardState,
		alarme,
		wetterAendern(neu: (s: WetterStand) => WetterStand) {
			stand = neu(stand);
			wetter.melden();
		}
	};
}

const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');

describe('F-A3: Alarme-Speicherer schreibt die Wetter-Einstellungen nicht still zurueck', () => {
	test('Radar an + Warnungen aus im Reiter Wetter, danach Cooldown in Zustellung ⇒ Radar und Warnungen bleiben', async () => {
		const h = await hub();
		h.wetterAendern((s) => ({ ...s, radarAn: true, warnungenAn: false }));
		await h.ctl.flush();
		assert.equal(puts().length, 1, 'Messaufbau: Wetter-PUT');
		assert.equal(server.stand(ID).radar_alert_enabled, true, 'Messaufbau: Radar gespeichert');

		h.wizardState.alertCooldownMinutes = 90;
		h.alarme.aenderungMelden();
		await h.ctl.flush();
		const lauf = h.ctl.laufendeSpeicherung;
		if (lauf) await lauf;

		const alarmPut = puts().at(-1)!;
		assert.equal((alarmPut.anfrage as Knoten).alert_cooldown_minutes, 90, 'Messaufbau: Cooldown-PUT');
		assert.notEqual((alarmPut.anfrage as Knoten).radar_alert_enabled, false, 'Alarm-PUT schreibt Radar aus dem alten Stand zurueck');
		const s = server.stand(ID);
		assert.equal(s.radar_alert_enabled, true, 'Radar wurde vom Alarme-Speicherer still ausgeschaltet');
		assert.equal((s.official_warnings as Knoten).enabled, false, 'Warnungen wurden vom Alarme-Speicherer still eingeschaltet');
		assert.equal(s.alert_cooldown_minutes, 90);
	});
});
