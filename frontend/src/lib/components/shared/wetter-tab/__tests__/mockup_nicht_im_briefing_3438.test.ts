// TDD RED — Issue #3438 (Epic #2913), Punkt 1: Chips „Nicht im Briefing“ im Mockup Fassung 4.
// Spec: docs/specs/modules/fix_3438_wetter_ganzseite.md — AC-1 (Trip, 11 Chips), AC-2 (Orte, 15 Chips).
//
// Nutzersicht: Der Bildprüfer meldet im Reiter Wetter „Trip 8 statt 11, Orte 10 statt 15 Chips“. Die
// Produktregel ist belegt (#2794 AC-19, #3047): jede ausgebbare, nicht gewählte Katalog-Metrik ist
// hinzufügbar, in Gruppen-Reihenfolge. Das Mockup (und die daraus erzeugte Elementliste, die der
// Staging-Abgleich nutzt) muss genau diese Liste zeigen.
//
// Soll wird NICHT abgeschrieben, sondern aus dem Produkt-Modell berechnet:
//   - Seed-Konfiguration des Staging-Prüfkontos aus den echten Seed-Funktionen
//     (scripts/staging_pruefkonto_mockupdaten.py: soll_wetter(), soll_vergleich()),
//   - zentraler Katalog /api/metrics und Vergleichs-Katalog /api/compare/metrics aus denselben
//     Python-Funktionen wie im Betrieb (wetterTabDaten.ts), Auflösung der Vorlage über resolve_ampel,
//   - derselbe Ladeweg wie WetterTabInhalt.svelte: standAusAbo → briefingAngebot → metricLabel.
// Ist: Elementliste docs/context/einstellungen_neu/elementliste.json (Rolle chip, Schlüssel
// wetter.nicht_im_briefing.hinzufuegen, Reiter wetter, Zustand normal), Reihenfolge nach `ordnung`.
// Kein Mock.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/wetter-tab/__tests__/mockup_nicht_im_briefing_3438.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { REPO, aufgeloestVon, live, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { altSchluesselAusKatalog, briefingAngebot, eigenschaftenAusKatalog } from '../ampelModell.ts';
import { loadCompareSelectionEntries } from '../compareMetricCatalogLoader.ts';
import * as Z from '../wetterZustand.ts';
import { metricLabel } from '../../../../i18n/metricLabel.ts';

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

// ── Seed des Prüfkontos aus den echten Seed-Funktionen (keine Kopie der Listen) ─────────────────
const PY_SEED = [
	'import sys, json',
	"sys.path.insert(0, 'scripts'); sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'import staging_pruefkonto_mockupdaten as s',
	"trip = {'id': s.TRIP_ID, 'name': s.TRIP_NAME, 'stages': [], 'display_config': s.soll_wetter()}",
	"orte = {'id': 'gz2967-vergleich', **s.soll_vergleich([o[0] for o in s._ORTE], ['a@gz.invalid', 'b@gz.invalid'])}",
	"print(json.dumps({'trip': trip, 'orte': orte}, ensure_ascii=False))"
].join('\n');
const SEED: { trip: Json; orte: Json } = JSON.parse(execFileSync('uv', ['run', 'python3', '-c', PY_SEED], { cwd: REPO, encoding: 'utf-8' }).trim());

const LIVE = live();
const EIG = eigenschaftenAusKatalog(LIVE.metrics);
const zurueck = vergleichsKatalogFetch();
const KATALOG = await loadCompareSelectionEntries();
zurueck();
const ALT = altSchluesselAusKatalog(KATALOG);
const KATALOG_IDS = new Set<string>(KATALOG.flatMap((e: Json) => (e.metric_id ? [e.metric_id] : [])));

type Ctx = 'trip' | 'orte';
const KONTEXT: Record<Ctx, 'route' | 'vergleich'> = { trip: 'route', orte: 'vergleich' };
const ANZAHL: Record<Ctx, number> = { trip: 11, orte: 15 };

/** Soll: Chips „Nicht im Briefing“ so, wie das Produkt sie für das Prüfkonto rendert (Anzeigename DE). */
function sollChips(ctx: Ctx): string[] {
	const context = KONTEXT[ctx];
	const abo = ctx === 'trip' ? SEED.trip : SEED.orte;
	const stand = Z.standAusAbo(context, abo, aufgeloestVon(abo), context === 'vergleich' ? ALT : {}, { eig: EIG });
	return briefingAngebot(context, EIG, stand.auswahl, KATALOG_IDS).map((id) => {
		const e = EIG[id];
		return metricLabel({ label: e?.label_de ?? id, label_de: e?.label_de, label_en: e?.label_en }, 'de');
	});
}

const LISTE: Json[] = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf8')).elemente;

/** Ist: Chips der Elementliste (aus dem Mockup erzeugt) in Mockup-Reihenfolge, ohne „+ “. */
function mockupChips(ctx: Ctx, zustand = 'normal'): string[] {
	return LISTE.filter(
		(e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === zustand && e.rolle === 'chip' && e.i18n_key === 'wetter.nicht_im_briefing.hinzufuegen'
	)
		.sort((a, b) => a.ordnung - b.ordnung)
		.map((e) => String(e.text_de).replace(/^\+\s*/, ''));
}

describe('#3438 Vorbedingung: Produkt-Soll für das Prüfkonto', () => {
	for (const ctx of ['trip', 'orte'] as Ctx[]) {
		test(`${ctx}: briefingAngebot liefert ${ANZAHL[ctx]} Chips (Staging-Messung 28.11.)`, () => {
			assert.equal(sollChips(ctx).length, ANZAHL[ctx], `Produkt-Soll ${ctx}: ${sollChips(ctx).join(', ')}`);
		});
	}
});

describe('#3438 AC-1/AC-2: Mockup-Chips „Nicht im Briefing“ = Produkt-Angebot (Anzahl und Reihenfolge)', () => {
	for (const ctx of ['trip', 'orte'] as Ctx[]) {
		test(`AC-${ctx === 'trip' ? 1 : 2} (${ctx}): Elementliste zeigt dieselben ${ANZAHL[ctx]} Chips in Produkt-Reihenfolge`, () => {
			assert.deepEqual(mockupChips(ctx), sollChips(ctx), `Mockup-Chips ${ctx} weichen vom Produkt-Angebot ab`);
		});
	}
});
