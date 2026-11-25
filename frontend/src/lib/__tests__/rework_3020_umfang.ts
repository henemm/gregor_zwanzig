// Umfang des Rückbaus #3020 (Spec docs/specs/modules/rework_3020_altbausteine_entfernen.md).
// Gemeinsame Quelle für Rückbau-Wächter und Probe-Löschung. Fällt mit dem letzten Wächter.
// Pfade relativ zu `frontend/src/lib/components/`.

export type Scheibe = 2 | 3 | 4;

const unter = (ordner: string, namen: string): string[] =>
	namen
		.trim()
		.split(/\s+/)
		.map((n) => `${ordner}/${n}`);

export const SCHEIBEN: Record<Scheibe, string[]> = {
	2: [
		...unter('compare', 'compareHourlyMetricDefs.ts hourlyFriendlyMap.ts layoutPreviewRows.ts versandPropsAus.ts wetterMetrikenPropsAus.ts'),
		...unter('organisms', 'AlertsCard.svelte MetricOffShelf.svelte OutboxCard.svelte PresetRail.svelte'),
		...unter('shared', 'OutputLayoutEditor.svelte layout-tab/channelLayoutsDirty.ts layout-tab/ltIdealRange.ts'),
		...unter('trip-detail', 'TablePreview.svelte WeatherV2Kanaele.svelte ActiveMetricRow.svelte BucketSection.svelte BucketSectionOff.svelte ChannelLimitMarkers.svelte PresetRow.svelte')
	],
	3: [
		...unter('molecules', 'GrundauswahlLeerHinweis.svelte'),
		...unter('trip-detail', 'BriefingScheduleTab.svelte weatherSaveGate.ts'),
		...unter('shared', 'WetterMetrikenVersandPanel.svelte WeatherMetricsTab.svelte OutlookLayoutControls.svelte reportConfigDirty.ts'),
		...unter('shared/layout-tab', 'LayoutTab.svelte LTCapNote.svelte LTChannelPicker.svelte LTCutLine.svelte'),
		...unter(
			'shared/weather-metrics-tab',
			`AggregationMetricRow.svelte MultiSymbolMetricRow.svelte ThresholdMetricRow.svelte
			 WeatherV2Grundauswahl.svelte WeatherV2PresetBar.svelte WeatherV2Reihenfolge.svelte
			 channelMetricLayouts.ts compareAggregationGrouping.ts kuerzelLegende.ts kuerzelMarken.ts
			 nurEinBericht.ts outlookFriendlyCapability.ts weatherMetricsSavePayload.ts
			 weatherMetricsTabSections.ts wertebereicheAnzeige.ts`
		)
	],
	4: [
		...unter('shared', 'VersandTab.svelte MailInhaltCard.svelte'),
		...unter(
			'shared/versand-tab',
			`VTBriefingChannels.svelte VTLaufzeitRoute.svelte VTLaufzeitVergleich.svelte
			 VTNextBriefing.svelte VTSchedulePlan.svelte channelContactLabel.ts vtBriefingChannelsText.ts`
		)
	]
};

/** In der Spec genannte Länge je Scheibe (Vakuum-Schutz, AC-3). */
export const ANZAHL: Record<Scheibe, number> = { 2: 19, 3: 26, 4: 9 };

/** Nie löschen (Spec, Abschnitt Scope) — Dateinamen, der Ordner wird gesucht. */
export const BLEIBT = [
	'channelConnectionStatus.ts',
	'sendTargetLabel.ts',
	'dayWindowClamp.ts',
	'nextBriefingText.ts',
	'naechstesBriefingLader.svelte.ts',
	'nextBriefingLoad.ts',
	'reportConfigPayload.ts',
	'mergeReportConfig.ts',
	'ltChannels.ts',
	'kanalStilSpeicherung.ts',
	'weatherMetricsCompareSave.ts',
	'compareChannelMetricLayouts.ts',
	'mailInhaltZustand.ts',
	'mailInhaltKonstanten.ts',
	'pickEigenfelder.ts'
];

/**
 * Tests, die lebendes Verhalten prüfen und in der Probe-Löschung nur wegen eines geteilten
 * Testhelfers rot sind (AC-11). Nach S1 müssen sie dort grün sein. Relativ zu `frontend/src/`.
 */
export const LEBENDE_HELFER_NUTZER: string[] = [
	'lib/__tests__/trip_nach_412_folgeschreiben_traegt_altes_if_match.test.ts',
	...unter(
		'lib/components/trip-detail/__tests__',
		`trip_retry_adoption_schutz.test.ts trip_konflikt_schreibt_seitenstand_fort.test.ts
		 trip_reiter_nutzlast_nur_eigene_felder.test.ts trip_retry_reiterwechsel_eingabe_bleibt.test.ts
		 trip_python_skip_next_ohne_412.test.ts trip_retry_nach_reiterwechsel.test.ts
		 trip_reiter_roundtrip_jedes_feld.test.ts trip_mehrreiter_nach_412_kein_verlust.test.ts
		 trip_retry_fehlerpfade_kein_verlust.test.ts tempo_je_etappe_3197.test.ts
		 tempo_je_etappe_3197_fixloop1.test.ts tempo_je_etappe_3197_fixloop4.test.ts
		 tempo_je_etappe_3197_mobil.test.ts tempo_karte_3196.test.ts
		 tempo_panel_3196_fixloop3.test.ts trip_header_status_profil.test.ts`
	),
	...unter(
		'lib/components/shared/hub-kopf/__tests__',
		'hub_kopf_c2_bildabgleich.test.ts hub_kopf_c2_mockup.test.ts hub_kopf_seiten_paritaet.test.ts'
	),
	...unter('lib/components/trip-new/__tests__', 'tempo_je_etappe_3197_anlegen_verdrahtung.test.ts trip_anlegen_sprache.test.ts'),
	'routes/gpx-upload/__tests__/gpx_upload_sprache.test.ts',
	'routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts'
];
