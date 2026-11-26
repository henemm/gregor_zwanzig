// TDD RED — Issue #3364: Größen mit Bericht-Flags („nur morgens“ / „nur abends“) im Reiter Wetter.
// Spec docs/specs/modules/fix_3364_nur_morgens_abends.md, Test Plan 1 bis 3, AC-1 bis AC-4.
// Kontext docs/context/fix-3364-nur-morgens-abends.md, Entscheidungen 2 bis 5.
//
// Ganzer Weg mit den ECHTEN Funktionen (wie Describe „#3020 G44“ in was_steht_wo_karte.test.ts):
// Abo -> Reiter-Zustand (wetterZustand.standAusAbo, ampelModell) -> Geste („−“ ohneMetrik, „+“ mitMetrik)
// -> Speichernutzlast (wetterTabSpeicherung.tripNutzlast, ampelSchreiben) -> Python-Ausgabe
// (placementsOrakel: `resolve_channel_lists` je Briefing, derselbe Filter wie die Mail).
// Zwei Nutzer: jeder Fall läuft für Nutzer A und Nutzer B mit eigenem Abo.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/bericht_flags_3364.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WT = path.resolve(HERE, '..');

// cloud_mid nur morgens, gust nur abends (beide `enabled:false` mit Flag), wind morgens an / abends aus
// (bleibt unberührt), thunder ohne Flags. Zusatzfelder prüfen, dass Abwahl nur die Flags entfernt.
const BESTAND = [
	{ metric_id: 'cloud_mid', enabled: false, order: 0, bucket: 'primary', morning_enabled: true, format_mode: 'raw' },
	{ metric_id: 'gust', enabled: false, order: 1, bucket: 'primary', evening_enabled: true, sms_threshold: 40 },
	{ metric_id: 'wind', enabled: true, order: 2, bucket: 'primary', evening_enabled: false, use_friendly_format: true },
	{ metric_id: 'thunder', enabled: true, order: 3, bucket: 'primary' }
];
const EIGENE = BESTAND.map((m) => m.metric_id);
const NUTZER = ['bericht-flags-a', 'bericht-flags-b'] as const;
const FLAGS = ['morning_enabled', 'evening_enabled'];

async function modelle() {
	const lade = (datei: string): Promise<J> => import(pathToFileURL(path.join(WT, datei)).href);
	const [O, D, A, Z, S, G] = await Promise.all(
		['__tests__/placementsOrakel.ts', '__tests__/wetterTabDaten.ts', 'ampelModell.ts', 'wetterZustand.ts', 'wetterTabSpeicherung.ts', '__tests__/ausgabeOrakel.ts'].map(lade)
	);
	const vorlagen = A.vorlagenAusTemplates(D.live().templates);
	const eig = A.eigenschaftenAusKatalog(D.live().metrics);
	const abo = (nutzer: string, metrics: J[] = BESTAND): J => ({ id: `${nutzer}-abo`, display_config: { metrics: structuredClone(metrics) } });
	const stand = (x: J) => Z.standAusAbo('route', x, D.aufgeloestVon(x), {}, { eig });
	const nutzlast = (x: J, s: J): J[] => S.tripNutzlast({ client: null, stand: () => s, vorlagen: () => vorlagen, abo: () => x }).weatherConfig.metrics;
	const speichere = (x: J, s: J) => ({ id: x.id, display_config: G.ebene1(x.display_config, S.tripNutzlast({ client: null, stand: () => s, vorlagen: () => vorlagen, abo: () => x }).weatherConfig) });
	const orakel = (nutzer: string, x: J) => O.placementsOrakel([{ id: x.id, nutzer, kind: 'route', abo: x }])[0];
	const eigene = (liste: [string, unknown][]) => liste.map(([m]) => m).filter((m) => EIGENE.includes(m));
	return { abo, stand, nutzlast, speichere, orakel, eigene, Z };
}
const eintrag = (liste: J[], id: string): J => {
	const e = liste.filter((x) => x.metric_id === id);
	assert.equal(e.length, 1, `genau ein Eintrag ${id} in metrics[], gefunden ${e.length}`);
	return e[0];
};
const ohne = (e: J, schluessel: string[]): J => Object.fromEntries(Object.entries(e).filter(([k]) => !schluessel.includes(k)));

describe('#3364 Bericht-Flags im Reiter Wetter (Trip)', () => {
	for (const nutzer of NUTZER) {
		test(`AC-1 (${nutzer}): nur-morgens- und nur-abends-Größe erscheinen als gewählt, wie die Mail sie führt`, async () => {
			const m = await modelle();
			const x = m.abo(nutzer);
			const o = m.orakel(nutzer, x);
			// Messaufbau: die Mail führt cloud_mid nur morgens, gust nur abends.
			assert.ok(m.eigene(o.listen.morning.email).includes('cloud_mid'), 'Messaufbau: cloud_mid im Morgen-Briefing');
			assert.ok(!m.eigene(o.listen.evening.email).includes('cloud_mid'), 'Messaufbau: cloud_mid nicht im Abend-Briefing');
			assert.ok(m.eigene(o.listen.evening.email).includes('gust'), 'Messaufbau: gust im Abend-Briefing');
			assert.ok(!m.eigene(o.listen.morning.email).includes('gust'), 'Messaufbau: gust nicht im Morgen-Briefing');
			const auswahl: string[] = m.stand(x).auswahl;
			assert.ok(auswahl.includes('cloud_mid'), `nur morgens geführt, aber nicht gewählt: ${auswahl}`);
			assert.ok(auswahl.includes('gust'), `nur abends geführt, aber nicht gewählt: ${auswahl}`);
			assert.ok(auswahl.includes('wind') && auswahl.includes('thunder'), 'die übrigen Größen bleiben gewählt');
		});

		test(`AC-2 (${nutzer}): „−“ an einer nur-morgens-Größe setzt enabled:false, entfernt die Flags, übrige Felder identisch`, async () => {
			const m = await modelle();
			const x = m.abo(nutzer);
			// Schreibseite unabhängig vom Lesen (AC-1) gemessen: „−“ nimmt die Größe aus der Auswahl.
			const s = m.stand(x);
			const metrics = m.nutzlast(x, m.Z.ohneMetrik(s, 'cloud_mid'));
			const e = eintrag(metrics, 'cloud_mid');
			assert.equal(e.enabled, false);
			for (const f of FLAGS) assert.ok(!(f in e), `Schlüssel ${f} steht noch im abgewählten Eintrag: ${JSON.stringify(e)}`);
			assert.deepEqual(ohne(e, ['enabled', ...FLAGS]), ohne(BESTAND[0], ['enabled', ...FLAGS]), 'übrige Felder unverändert');
			// Python-Mail-Filter: in keinem Briefing mehr.
			const n = m.orakel(nutzer, m.speichere(x, m.Z.ohneMetrik(s, 'cloud_mid')));
			for (const rt of ['morning', 'evening']) assert.ok(!m.eigene(n.listen[rt].email).includes('cloud_mid'), `nach „−“ steht cloud_mid noch im Briefing ${rt}`);
		});

		test(`AC-2 (${nutzer}): „−“ an einer nur-abends-Größe nimmt sie aus beiden Briefings`, async () => {
			const m = await modelle();
			const x = m.abo(nutzer);
			const s = m.stand(x);
			const e = eintrag(m.nutzlast(x, m.Z.ohneMetrik(s, 'gust')), 'gust');
			assert.equal(e.enabled, false);
			for (const f of FLAGS) assert.ok(!(f in e), `Schlüssel ${f} steht noch im abgewählten Eintrag: ${JSON.stringify(e)}`);
			assert.deepEqual(ohne(e, ['enabled', ...FLAGS]), ohne(BESTAND[1], ['enabled', ...FLAGS]), 'übrige Felder unverändert');
			const n = m.orakel(nutzer, m.speichere(x, m.Z.ohneMetrik(s, 'gust')));
			for (const rt of ['morning', 'evening']) assert.ok(!m.eigene(n.listen[rt].email).includes('gust'), `nach „−“ steht gust noch im Briefing ${rt}`);
		});

		test(`AC-3 (${nutzer}): „+“ nach Abwahl setzt enabled:true ohne Flags, beide Briefings führen die Größe`, async () => {
			const m = await modelle();
			// Bestand nach einer früheren Abwahl, die die Flags noch stehen ließ (Altbestand vor dem Fix).
			const abgewaehlt = BESTAND.map((e) => (e.metric_id === 'cloud_mid' ? { ...e, enabled: false, morning_enabled: false } : e));
			const x = m.abo(nutzer, abgewaehlt);
			const s = m.stand(x);
			assert.ok(!s.auswahl.includes('cloud_mid'), 'Vorbedingung: cloud_mid ist in keinem Briefing, also nicht gewählt');
			const wieder = m.Z.mitMetrik(s, 'cloud_mid');
			const e = eintrag(m.nutzlast(x, wieder), 'cloud_mid');
			assert.equal(e.enabled, true);
			for (const f of FLAGS) assert.ok(!(f in e), `Schlüssel ${f} steht noch im wieder angewählten Eintrag: ${JSON.stringify(e)}`);
			const n = m.orakel(nutzer, m.speichere(x, wieder));
			for (const rt of ['morning', 'evening']) assert.ok(m.eigene(n.listen[rt].email).includes('cloud_mid'), `nach „+“ fehlt cloud_mid im Briefing ${rt}`);
		});

		test(`AC-4 (${nutzer}): unveränderte Einträge behalten ihre Flags beim Speichern`, async () => {
			const m = await modelle();
			const x = m.abo(nutzer);
			const s = m.stand(x);
			// Geste an einer anderen Größe (thunder abwählen); wind und die übrigen bleiben unberührt.
			const metrics = m.nutzlast(x, m.Z.ohneMetrik(s, 'thunder'));
			assert.deepEqual(eintrag(metrics, 'wind'), BESTAND[2], 'wind: Flags und Felder unverändert');
			assert.deepEqual(eintrag(metrics, 'cloud_mid'), BESTAND[0], 'cloud_mid (nur morgens, unberührt): Eintrag unverändert');
			assert.deepEqual(eintrag(metrics, 'gust'), BESTAND[1], 'gust (nur abends, unberührt): Eintrag unverändert');
		});
	}

	test('zwei Nutzer: die Abwahl bei Nutzer A ändert das Abo von Nutzer B nicht', async () => {
		const m = await modelle();
		const a = m.abo(NUTZER[0]);
		const b = m.abo(NUTZER[1]);
		const sa = m.stand(a);
		m.nutzlast(a, m.Z.ohneMetrik(sa, 'cloud_mid'));
		assert.deepEqual(b.display_config.metrics, BESTAND, 'Abo von B unverändert');
		const ob = m.orakel(NUTZER[1], b);
		assert.ok(m.eigene(ob.listen.morning.email).includes('cloud_mid'), 'B führt cloud_mid weiter morgens');
	});
});
