// Issue #3020 R1 (G18): jede Geste der vier Organismen des Reiters Zustellung (Briefing-Zeiten, Laufzeit,
// Kanal-Tabelle, Stille Stunden) meldet GENAU EINMAL an den EINEN Speicherer, und die Anzeige folgt.
//
// Gemessen im ECHTEN Instanz-Skript von ZustellungTab.svelte: je Einbettung wird der Ausdruck `onaendern={…}` gegen
// seine Umgebung ausgewertet und aufgerufen. Zwei Nutzer mit verschiedenen Abos (Trip A, Orte B).
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/organismen_melden_an_einen_speicherer_3020.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { attributAusdruck, findeKomponenten, umgebungFuer, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const REITER = resolve(HIER, '../ZustellungTab.svelte');
const ORGANISMEN = ['BriefingZeiten', 'LaufzeitKarte', 'KanalTabelle', 'StilleStunden'] as const;

/** Je Organismus eine Änderung, wie er sie als neuen Stand meldet, und der Owner, unter dem sie gespeichert wird. */
const GESTE: Record<(typeof ORGANISMEN)[number], { aendere: (s: Knoten) => Knoten; owner: Record<'route' | 'vergleich', string[]> }> = {
	BriefingZeiten: { aendere: (s) => ({ ...s, morgenZeit: '05:15' }), owner: { route: ['versand'], vergleich: ['versand'] } },
	// Eigene Laufzeit haben nur Orte; im Trip folgt sie den Etappen, es gibt nichts zu speichern.
	LaufzeitKarte: { aendere: (s) => ({ ...s, endDate: '2027-03-01' }), owner: { route: [], vergleich: ['versand'] } },
	KanalTabelle: { aendere: (s) => ({ ...s, briefing: { ...s.briefing, telegram: !s.briefing.telegram } }), owner: { route: ['versand'], vergleich: ['versand'] } },
	StilleStunden: { aendere: (s) => ({ ...s, stilleAn: true, stilleVon: '21:30', stilleBis: '05:30' }), owner: { route: ['alarme'], vergleich: ['alarme'] } }
};

const TRIP_A = { id: 'trip-a-g18', name: 'A', stages: [], report_config: { morning_time: '06:00:00', morning_enabled: true, send_email: true, send_telegram: false } };
const ORTE_B = { id: 'orte-b-g18', name: 'B', location_ids: [], morning_time: '07:00:00', morning_enabled: true, display_config: {} };

/** Eine frische Instanz je Geste; `gemeldet` = Aufrufe von `aenderungMelden` des einen Speicherers. */
async function instanz(context: 'route' | 'vergleich') {
	const geplant: string[] = [];
	const { ast, quelle, u } = await umgebungFuer(
		REITER,
		{
			context,
			versandSprung: 0,
			beispielAlarmRegeln: [],
			activation: undefined,
			onJump: undefined,
			untrack: (fn: () => unknown) => fn(),
			onMount: () => {},
			panel: {
				trip: context === 'route' ? structuredClone(TRIP_A) : undefined,
				preset: context === 'vergleich' ? structuredClone(ORTE_B) : undefined,
				saveController: { schedule: (_fn: unknown, _ms: number, owner: string) => void geplant.push(owner), cancel: () => {} }
			}
		},
		{ jsAlsTs: true }
	);
	assert.ok(u.speicherung, 'Messaufbau: der echte Speicherer entsteht');
	const gemeldet: Knoten[] = [];
	const echt = u.speicherung.aenderungMelden.bind(u.speicherung);
	u.speicherung.aenderungMelden = (s: Knoten) => {
		gemeldet.push(structuredClone(s));
		echt(s);
	};
	return { ast, quelle, u, gemeldet, geplant };
}

describe('#3020 G18: EIN Speicherer im Reiter Zustellung', () => {
	test('alle_vier_organismen_melden_genau_einmal_an_den_einen_speicherer', async () => {
		for (const context of ['route', 'vergleich'] as const) {
			for (const name of ORGANISMEN) {
				const wo = `${context}/${name}`;
				const { ast, quelle, u, gemeldet, geplant } = await instanz(context);
				const einbettungen = findeKomponenten(ast, name);
				assert.equal(einbettungen.length, 1, `${wo}: genau eine Einbettung`);
				const ausdruck = attributAusdruck(einbettungen[0], quelle, 'onaendern');
				assert.ok(ausdruck, `${wo}: Einbettung ohne onaendern`);
				const neu = GESTE[name].aendere(structuredClone(u.stand));
				(werte(ausdruck, u) as (s: Knoten) => void)(neu);
				assert.equal(gemeldet.length, 1, `${wo}: genau eine Meldung an den Speicherer`);
				assert.deepEqual(gemeldet[0], neu, `${wo}: gemeldet wird der neue Stand`);
				assert.deepEqual(u.stand, neu, `${wo}: die Anzeige folgt`);
				assert.deepEqual(geplant, GESTE[name].owner[context], `${wo}: geplante Vorgänge`);
			}
		}
	});
});
