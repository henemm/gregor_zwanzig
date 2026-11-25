// Issue #3047 Runde 7, Befund E4: Amtliche Warnungen im Altbestand-Mischzustand.
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md („Nachtrag Runde 7",
// PO-Entscheidung 2026-11-16, AC-26).
//
// PO-Regel (Trip und Orte): Ist der Briefing-Schalter (`official_alerts_enabled`) ODER der
// Alarm-Schalter (`official_warnings.enabled`, Altfeld `official_alert_triggers_enabled`) an, gilt
// „beides an"; der Editor zeigt „an". Nur wenn beide aus sind: „aus". Damit loest diese Regel die
// ODER-Regel aus feat_2794 AC-20 ab (dort zaehlte `official_alerts_enabled` nur, wenn
// `official_warnings` vorhanden war, und ein fehlendes Briefing-Feld zaehlte als „aus").
//
// Gemessen dort, wo es wirkt: Lesen (`standAusAbo`, Reiter Wetter), die echte Speicher-Nutzlast
// (unbeteiligte Speicherung = Read-Modify-Write, `sources` bleibt) und Gleichheit mit der
// Python-Lesefunktion, die Briefing und Alarm steuert (`services/amtliche_warnungen_schalter.py`).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/e4_amtliche_warnungen_mischzustand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';

import { aufgeloestVon, live, REPO } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';

const vorlagen = () => vorlagenAusTemplates(live().templates);

type Fall = { name: string; felder: Record<string, unknown>; an: boolean };

// Dieselben Faelle wie tests/tdd/test_3047_e4_amtliche_warnungen_beides_an.py (fehlendes Feld = nicht gesetzt).
const FAELLE: Fall[] = [
	{ name: 'briefing_aus_alarm_altfeld_default', felder: { official_alerts_enabled: false }, an: true },
	{ name: 'briefing_aus_alarm_an_migriert', felder: { official_alerts_enabled: false, official_warnings: { enabled: true } }, an: true },
	{ name: 'briefing_an_alarm_aus_migriert', felder: { official_alerts_enabled: true, official_warnings: { enabled: false } }, an: true },
	{ name: 'briefing_fehlt_alarm_aus_migriert', felder: { official_warnings: { enabled: false } }, an: true },
	{ name: 'briefing_an_alarm_altfeld_aus', felder: { official_alerts_enabled: true, official_alert_triggers_enabled: false }, an: true },
	{ name: 'nur_sources', felder: { official_warnings: { sources: ['meteoalarm'] } }, an: true },
	{ name: 'leeres_official_warnings', felder: { official_warnings: {}, official_alert_triggers_enabled: false }, an: true },
	{ name: 'briefing_aus_ow_ohne_enabled', felder: { official_alerts_enabled: false, official_warnings: { sources: ['dwd'] } }, an: true },
	{ name: 'beides_aus', felder: { official_alerts_enabled: false, official_warnings: { enabled: false } }, an: false },
	{ name: 'beides_aus_altfeld', felder: { official_alerts_enabled: false, official_alert_triggers_enabled: false }, an: false },
	{ name: 'beides_aus_leeres_ow', felder: { official_alerts_enabled: false, official_warnings: {}, official_alert_triggers_enabled: false }, an: false },
	{ name: 'nie_eingestellt', felder: {}, an: true }
];

function abo(kontext: 'route' | 'vergleich', felder: Record<string, unknown>): AboSicht {
	const basis: AboSicht = kontext === 'route'
		? { id: 'trip-e4', profil: 'wandern', report_config: { day_window_start_hour: 6, day_window_end_hour: 18 },
			display_config: { metrics: [{ metric_id: 'wind', enabled: true }], ampel: { template: 'wandern' } } }
		: { id: 'cmp-e4', profil: 'wandern', display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }], ampel: { template: 'wandern' } } };
	return { ...basis, ...structuredClone(felder) } as AboSicht;
}

const PY_REGEL = [
	'import json, sys',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from services.amtliche_warnungen_schalter import amtliche_warnungen_an_preset',
	'print(json.dumps([amtliche_warnungen_an_preset(f) for f in json.loads(sys.stdin.read())]))'
].join('\n');

function pythonRegel(felder: Record<string, unknown>[]): boolean[] {
	const out = execFileSync('uv', ['run', 'python3', '-c', PY_REGEL], { cwd: REPO, encoding: 'utf-8', input: JSON.stringify(felder) });
	return JSON.parse(out.trim());
}

for (const kontext of ['route', 'vergleich'] as const) {
	describe(`E4 ${kontext}: Reiter Wetter zeigt „beides an", sobald Briefing ODER Alarm an ist`, () => {
		for (const f of FAELLE) {
			test(`e4_${kontext}_lesen_${f.name}_ist_${f.an}`, () => {
				const s = standAusAbo(kontext, abo(kontext, f.felder), aufgeloestVon(abo(kontext, f.felder)));
				assert.equal(s.warnungenAn, f.an, `${f.name}: ${JSON.stringify(f.felder)}`);
			});
		}
	});

	describe(`E4 ${kontext}: unbeteiligte Speicherung schreibt beide Felder = angezeigter Wert, Rest bleibt`, () => {
		for (const f of FAELLE) {
			test(`e4_${kontext}_speichern_${f.name}`, () => {
				const a = abo(kontext, f.felder);
				const v = vorlagen();
				const s = standAusAbo(kontext, a, aufgeloestVon(a));
				const opt = { client: null as never, stand: () => s, vorlagen: () => v, abo: () => a };
				const felder = kontext === 'route' ? tripNutzlast(opt).tripFelder : vergleichNutzlast(opt);
				const ow = (f.felder.official_warnings ?? {}) as Record<string, unknown>;
				assert.equal(felder.official_alerts_enabled, f.an, 'Briefing-Schalter');
				assert.deepEqual(felder.official_warnings, { ...ow, enabled: f.an }, 'Alarm-Schalter, sources erhalten');
				assert.deepEqual(a, abo(kontext, f.felder), 'Lese-Bestand unveraendert');
			});
		}
	});
}

describe('E4: Editor-Regel gleich der Python-Lesefunktion (Briefing und Alarm)', () => {
	test('e4_paritaet_python_alle_faelle', () => {
		const py = pythonRegel(FAELLE.map((f) => f.felder));
		const ts = FAELLE.map((f) => standAusAbo('vergleich', abo('vergleich', f.felder), aufgeloestVon(abo('vergleich', f.felder))).warnungenAn);
		assert.deepEqual(ts, py, FAELLE.map((f) => f.name).join(', '));
		assert.deepEqual(py, FAELLE.map((f) => f.an));
	});
});
