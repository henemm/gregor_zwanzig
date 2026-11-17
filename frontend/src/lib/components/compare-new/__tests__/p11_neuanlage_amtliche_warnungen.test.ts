// Issue #3047 Runde 7, Paket p11: Orts-Vergleich anlegen — amtliche Warnungen „an".
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md („Nachtrag Runde 7",
// PO 2026-11-16 „Amtliche Warnungen Neuanlage", loest #1258 AC-4 ab): neue Orts-Vergleiche
// bekommen Warnungen im Briefing UND als Alarm; beide Felder reisen ausdruecklich `true`.
//
// Gemessen dort, wo es wirkt: Standard-Feldsatz des Anlege-Editors (CompareNewEditor startet
// damit) -> Reiter Wetter (`standAusAbo`), Schritt Zustellung (`alarmePropsAus`, Wertprop des
// AlarmeTab) und der echte POST-Rumpf (`buildNewComparePresetPayload`).
// Trip-Pendant: trip-new/__tests__/fixloop3_c3_amtliche_warnungen_ein_eigentuemer.test.ts.
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/p11_neuanlage_amtliche_warnungen.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildNewComparePresetPayload, compareFeldsatzStandard } from '../../compare/compareEditorSave.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { amtlicheWarnungenAn } from '../../shared/wetter-tab/amtlicheWarnungen.ts';
import { standAusAbo, type AboSicht } from '../../shared/wetter-tab/wetterZustand.ts';
import { vorlagenAusTemplates } from '../../shared/wetter-tab/ampelModell.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

test('p11 Vergleich anlegen: Reiter Wetter und Zustellung zeigen „an"', () => {
	const wiz = compareFeldsatzStandard();
	const abo = {
		id: 'cmp-neu', profil: 'wandern', display_config: {},
		official_alerts_enabled: wiz.officialAlertsEnabled,
		official_warnings: { enabled: wiz.officialWarningsEnabled }
	} as unknown as AboSicht;
	assert.equal(standAusAbo('vergleich', abo, vorlagenAusTemplates(live().templates)).warnungenAn, true, 'Reiter Wetter');
	assert.equal(alarmePropsAus(wiz).officialWarningsEnabled, true, 'Schalter im Schritt Zustellung zeigt „aus"');
});

test('p11 Vergleich anlegen: POST traegt beide Warn-Felder ausdruecklich true', () => {
	const body = buildNewComparePresetPayload({ ...compareFeldsatzStandard(), alertChannels: undefined } as never);
	assert.equal(body.official_alerts_enabled, true, 'Briefing-Feld');
	assert.deepEqual(body.official_warnings, { enabled: true }, 'Alarm-Feld');
	assert.equal(amtlicheWarnungenAn(body as never), true);
});
