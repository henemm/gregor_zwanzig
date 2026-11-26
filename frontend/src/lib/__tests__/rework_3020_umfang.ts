// Umfang des Rückbaus #3020, Spec 2.0 (docs/specs/modules/rework_3020_altbausteine_entfernen.md, R2).
// Gemeinsame Quelle für Rückbau-Wächter und Probe-Löschung. Pfade relativ zu `frontend/src/lib/components/`.

const unter = (ordner: string, namen: string): string[] =>
	namen
		.trim()
		.split(/\s+/)
		.map((n) => `${ordner}/${n}`);

/**
 * Restbestand, den R2 löscht. Die Spec nennt 42 Dateien; 23 davon haben die Waisen-Scheiben #3383 (S1), #3384 (S4)
 * und #3385 (S3) schon entfernt (compare: layoutPreviewRows, versandPropsAus, wetterMetrikenPropsAus; molecules:
 * GrundauswahlLeerHinweis; shared: reportConfigDirty; shared/weather-metrics-tab: neun Dateien; trip-detail:
 * WeatherV2Kanaele, weatherSaveGate; shared/versand-tab: VTBriefingChannels, VTLaufzeitRoute, VTLaufzeitVergleich,
 * VTNextBriefing, VTSchedulePlan, channelContactLabel, vtBriefingChannelsText). Sie stehen hier nicht mehr: ihre Löschung und Importfreiheit bewacht
 * trip_pfad_altfeld_loeschnachweis_3297.test.ts, dessen Wortscan (F004) den Namen eines dieser Bauteile überall verbietet.
 */
export const RESTBESTAND: string[] = [
	...unter('compare', 'compareHourlyMetricDefs.ts hourlyFriendlyMap.ts'),
	...unter('organisms', 'AlertsCard.svelte MetricOffShelf.svelte OutboxCard.svelte PresetRail.svelte'),
	...unter('shared', 'OutputLayoutEditor.svelte'),
	...unter('shared/layout-tab', 'LTCapNote.svelte LTChannelPicker.svelte LTCutLine.svelte LayoutTab.svelte channelLayoutsDirty.ts ltIdealRange.ts'),
	...unter(
		'trip-detail',
		`ActiveMetricRow.svelte BucketSection.svelte BucketSectionOff.svelte ChannelLimitMarkers.svelte PresetRow.svelte
		 TablePreview.svelte`
	)
];

/** In der Spec genannte Länge (Vakuum-Schutz, AC-7). */
export const SPEC_ANZAHL = 42;
/** Davon schon durch #3383/#3384/#3385 entfernt (siehe oben). */
export const DURCH_WAISEN_ENTFERNT = 23;
/** Verbleibender Restbestand für R2. */
export const RESTBESTAND_ANZAHL = 19;

/** Barrel-Zeilen, die mit R2 fallen: [Barrel, Name]. */
export const BARREL: readonly (readonly [string, string])[] = [
	['organisms/index.ts', 'OutputLayoutEditor'],
	['organisms/index.ts', 'OutboxCard'],
	['organisms/index.ts', 'AlertsCard'],
	['organisms/index.ts', 'PresetRail'],
	['organisms/index.ts', 'MetricOffShelf'],
	['trip-detail/index.ts', 'TablePreview']
];

/** Nie löschen (Spec, Abschnitt Scope): Dateinamen, der Ordner wird gesucht. */
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
 * Tests, die lebendes Verhalten prüfen und ohne den Restbestand grün sein müssen. Relativ zu `frontend/src/`.
 * `trip_python_skip_next_ohne_412` und `wetter_tab_karte_mitspeichern_3020` hat #3357 gelöscht bzw. nie übernommen:
 * R1 stellt sie wieder her (AC-2, AC-3, R2-F4).
 */
export const LEBENDE_HELFER_NUTZER: string[] = [
	'lib/__tests__/trip_nach_412_folgeschreiben_traegt_altes_if_match.test.ts',
	'lib/components/organisms/__tests__/wetter_tab_karte_mitspeichern_3020.test.ts',
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

/**
 * R2 (Nachtrag 2026-11-26): Testdateien, die die Probe-Löschung der 11 Restdateien rot gemacht hat (Differenz zur
 * Baseline derselben Umgebung), plus ein Python-Fall. Pfade ab Repo-Wurzel; je Eintrag ein Entscheid in der Testtabelle (AC-8).
 */
export const ROT_R2: string[] = [
	...[
		'components/molecules/issue_578_molecules_organisms.test.ts',
		'components/shared/__tests__/OutputLayoutEditor.test.ts',
		'components/trip-detail/bug_499_skala_label.test.ts',
		'components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts',
		'components/trip-detail/__tests__/trip_hub_sprache.test.ts',
		'components/__tests__/bausteine_sprache.test.ts',
		'i18n/__tests__/katalog_schluessel_haben_verwender.test.ts',
		'i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts',
		'i18n/__tests__/reaktivitaet_waechter.test.ts',
		'__tests__/bausteine_waechter.test.ts',
		'__tests__/ink4_waechter.test.ts',
		'__tests__/rework_3020_rueckbau_waechter.test.ts',
		'__tests__/rework_3020_probe_loeschung.test.ts'
	].map((p) => `frontend/src/lib/${p}`),
	'tests/tdd/test_issue_289_surface_tokens.py::test_preset_row_color_mix_uses_surface0'
];
