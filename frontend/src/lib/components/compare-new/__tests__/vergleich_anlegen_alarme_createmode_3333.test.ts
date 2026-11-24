// Issue #3333 (Teil D2 von #3307), Adversary-Finding F001: AC-10 der Spec
// docs/specs/modules/feat_3333_zustellung_anlegen_orte.md — im Orte-Anlegen hat jede Alarm-Einstellung genau
// eine Bedienstelle; Alarm-Kanäle, Cooldown und Stille Stunden stehen nur im Reiter Zustellung.
//
// Wirkort: die beiden `<AlarmeTab …>`-Einbettungen im CompareNewEditor (Desktop + Mobil). Der Editor-SSR
// (vergleich_anlegen_zustellung_ssr_3333) sieht den Reiter Alarme nie, weil er erst hinter
// `{#if alarmeHydrated}` (gesetzt in onMount) steht; alarme_tab_ohne_zustellung_3333 rendert den Reiter direkt.
// Daher hier der Weg dazwischen, ohne Mock-Theater:
//   1. ECHTES Instanz-Skript des Editors (svelteInstanzPruefstand), onMount ECHT ausgeführt ->
//      hydrateAlarmeTab setzt `alarmeHydrated` (Netz nur gesät, entscheidet nichts).
//   2. Je Einbettung (0 = Desktop, 1 = Mobil) die ECHTEN Attribut- und Spread-Ausdrücke in der Umgebung des
//      Editor-Skripts ausgewertet.
//   3. Mit genau diesen Props den ECHTEN AlarmeTab serverseitig gerendert und die Abschnitte gezählt.
// Fehlt `createMode` an einer Einbettung, zeigt deren Reiter Kanäle/Cooldown/Stille erneut -> rot.
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/vergleich_anlegen_alarme_createmode_3333.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { findeKomponenten, werte, ohneTypen, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { COMPARE_EDITOR, editorUmgebung, mountenUndWarten, derivedNeu } from '../../shared/__tests__/standardwerteEditorPruefstand.ts';
import { MATCH_MEDIA, fetchMitschnitt } from '../../shared/__tests__/compareNeuEditorPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const AlarmeTab = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href)).default;

const ZUSTELLUNG = ['channels', 'cooldown', 'quiet-hours'];
const BLEIBEN = ['official-warnings', 'radar', 'metric-levels'];

/** Props einer Einbettung: Attribute und Spreads in Quelltext-Reihenfolge, ausgewertet im Editor-Skript. */
function propsDer(einbettung: Knoten, quelle: string, u: Knoten): Knoten {
	const props: Knoten = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type === 'SpreadAttribute') Object.assign(props, werte(ohneTypen(quelle, a.expression), u) as Knoten);
		else if (a.type === 'Attribute') {
			if (a.value === true) props[a.name] = true;
			else if (a.value?.type === 'ExpressionTag') props[a.name] = werte(ohneTypen(quelle, a.value.expression), u);
			else if (Array.isArray(a.value)) props[a.name] = a.value.map((t: Knoten) => (t.type === 'Text' ? t.data : werte(ohneTypen(quelle, t.expression), u))).join('');
			else props[a.name] = werte(a.name, u);
		}
	}
	return props;
}

function abschnitte(html: string): string[] {
	return [...html.matchAll(/data-testid="alarme-section-([a-z-]+)"/g)].map((m) => m[1]);
}

describe('#3333 F001 (AC-10): Reiter Alarme im Orte-Anlegen, gemountet wie im Editor', () => {
	test('Desktop und Mobil: hydriert, ohne Kanäle/Cooldown/Stille; Warnungen, Radar, Metrik-Stufen bleiben', async () => {
		const netz = fetchMitschnitt();
		try {
			const e = await editorUmgebung(COMPARE_EDITOR, {
				stateOverride: { name: 'Neu-3333', pickedIds: ['loc-a', 'loc-b'], activeTab: 'zustellung', zustellungVisited: true, metrikenVisited: true },
				vorlage: null,
				locations: [],
				window: MATCH_MEDIA
			});
			assert.equal(e.u.alarmeHydrated, false, 'Messaufbau: Reiter Alarme vor onMount schon freigegeben');
			await mountenUndWarten(e);
			for (let i = 0; i < 20 && e.u.alarmeHydrated !== true; i++) await new Promise((r) => setImmediate(r));
			assert.equal(e.u.alarmeHydrated, true, 'Messaufbau: hydrateAlarmeTab hat den Reiter Alarme nicht freigegeben');
			derivedNeu(e);

			const einb = findeKomponenten(e.ast, 'AlarmeTab');
			assert.equal(einb.length, 2, `CompareNewEditor bettet ${einb.length} statt 2 AlarmeTab ein (Desktop + Mobil)`);
			for (const [i, k] of einb.entries()) {
				const ansicht = i === 0 ? 'Desktop' : 'Mobil';
				const props = propsDer(k, e.quelle, e.u);
				assert.equal(props.context, 'vergleich', `${ansicht}: context`);
				const html = render(AlarmeTab, { props: { ...props, profileOverride: { premium_sms_allowed: true } } }).body;
				const ids = abschnitte(html);
				assert.ok(ids.length > 0, `${ansicht}: Messaufbau — keine Abschnitte gerendert`);
				for (const s of ZUSTELLUNG)
					assert.ok(!ids.includes(s), `${ansicht}: Abschnitt "${s}" im Reiter Alarme — zweite Bedienstelle neben dem Reiter Zustellung (createMode fehlt?) — ${JSON.stringify(ids)}`);
				for (const s of BLEIBEN) assert.ok(ids.includes(s), `${ansicht}: Abschnitt "${s}" fehlt — ${JSON.stringify(ids)}`);
			}
		} finally {
			netz.abbauen();
		}
	});
});
