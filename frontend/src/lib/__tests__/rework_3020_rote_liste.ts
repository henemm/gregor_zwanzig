// Rote Liste des Rückbaus #3020 (AC-4): die Testdateien der Probe-Löschung (Erstmessung 25.11.2026, 160 Dateien, dazu
// `weather_metric_kuerzel_marken`, schon vorher rot, liest `WeatherMetricsTab`). Eingefroren: sie misst die Testtabelle
// auch dann noch, wenn die Testdateien selbst mit ihrer Scheibe gelöscht sind. Nie kürzen. Relativ zu `frontend/src/`.

const NAMEN: Record<string, string> = {
	'lib/__tests__': 'bausteine_waechter ink4_waechter trip_nach_412_folgeschreiben_traegt_altes_if_match',
	'lib/components/__tests__': 'bausteine_sprache f13_ausdruck_offen_sprache',
	'lib/components/alerts-tab': 'issue_850_alert_metrics_stale',
	'lib/components/compare/__tests__': `
		compare_empty_metric_selection compare_feldsatz_roundtrip_datenerhalt compare_hourly_metric_formats_persistenz
		compare_layout_tab_dissolution compare_versand_hydration_unter_wetter_metriken compare_wetter_metriken_wertprops
		fix_3061_hub_hydrierer totcode_rueckbau_speicherweg versand_panel_ohne_wrapper_div
	`,
	'lib/components/compare': 'compareEditorHourlyMetrics feat3276_vergleich_ohne_altfelder layoutPreviewRows',
	'lib/components/edit/__tests__': 'report_config_uses_shared_schedule',
	'lib/components/molecules': 'issue_578_molecules_organisms',
	'lib/components/organisms/__tests__': 'feat_3190_vorlage_dialog_inline',
	'lib/components/shared/__tests__': `
		OutputLayoutEditor anlegeseiten_ohne_versand_panel_3333 ausblick_ein_name_3155 channelMetricLayouts
		channelOffGroupListBuilding channelPayloadAllChannels compareMetricOrder
		compare_outlook_metric_selection_structure compare_versand_wertprops context_herkunft_zweige_eingefroren
		hub_geteilte_felder_cooldown_quiet_konsistent hub_reiter_gemeinsame_aufloesung infobox_nur_beim_anlegen
		kanal_abwahl_hinweis mail_inhalt_card mail_inhalt_card_hub_einbindung mail_inhalt_haken_grosswetterlage_3237
		mail_inhalt_rueckbau_waechter mail_inhalt_zustand metricKuerzelLegende officialAlertLegend
		official_alerts_single_control_ui outlook_email_only_hint_per_context outlook_erbt_grundauswahl_structure
		outlook_restore_schreibt_nur_outlook_metrics reiter_sprunglinks_nur_neue_kennungen reportConfigDirty
		s3a2794_eine_wmt_instanz s3a2794_speicher_owner_waechter s3a2794_zustellung_ziel_und_bereich
		s3b2795_zustellung_profil_einmal speicher_anzeige_zwischenstand_wetter_und_briefing
		telegram_kurzstil_shared_toggle versand_tab_laedt_keine_compare_klebeschicht
		versand_tab_meldet_aenderungen_reaktiv versand_vergleich_premium_sms weatherMetricsTabSharing
		weather_metric_kuerzel_marken weather_metric_name_forms_visible weather_metrics_tab_compare_catalog_fetch
		weather_metrics_tab_create_mode_callback weather_metrics_tab_vergleich_uebersicht_kanal_tabs
		wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte
		wetter_metriken_versand_panel_fuehrt_sprung_nach wetter_metriken_versand_panel_paritaet
		wetter_metriken_versand_panel_speicherung wetter_metriken_vorlage_anwenden_sendet_ampel
	`,
	'lib/components/shared/hub-kopf/__tests__': 'hub_kopf_c2_bildabgleich hub_kopf_c2_mockup hub_kopf_seiten_paritaet',
	'lib/components/shared/layout-tab/__tests__': 'channelLayoutsDirty channelLimitModel layout_korridor_sprache',
	'lib/components/shared/layout-tab': 'ltIdealRange',
	'lib/components/shared/versand-tab/__tests__': `
		channelContactLabel channel_checkbox_dedupe_render compare_versand_zeigt_schaltbare_premium_sms
		merge_report_config_read_modify_write naechstes_briefing_baustein_render naechstes_briefing_verdrahtung
		premium_sms_context_gating_render shared_schedule_quickpick sms_unbestaetigt_kanalstatus
		telegram_unterzeile_render versand_tab_defaults_gleich_auslieferung versand_tab_sprache
		versand_telegram_je_kontext versand_texte_ohne_wertung_en vtBriefingChannelsText
		vtBriefingChannelsTextNoJudgement vt_schedule_plan_hour_step
	`,
	'lib/components/shared/weather-metrics-tab/__tests__': `
		aggregation_row_multi_select altfelder_gesperrt_s1c3 bug_2454_channel_ableitung_und_toggle
		compareAggregationGrouping daywindowcard_rueckbau_waechter editor_aenderung_gleich_erwartung
		editor_anzeige_gleich_erwartung editor_speichern_ohne_aenderung editor_standard_gleich_mail
		feld_erhalt_ohne_ausnahme lade_kanal_layouts_aus_trip multiSymbolMetricRowWiring neue_metrik_in_allen_listen
		neue_metrik_in_allen_listen_orte nur_ein_bericht_kennzeichnung outlookFriendlyCapabilityDrift
		s3a2794_bereich_filter sms_reiter_roh_einfach_nur_fuer_sms_format_capable speichern_sendet_alle_kanaele
		speichern_waehlt_richtigen_bestand telegram_kanalgrenze_je_kontext telegram_schnittlinie_wahr
		thunderThresholdCatalogGuard thunderThresholdLevels vorlage_anwenden_uebernimmt_ampel
		vorlage_speichern_karte_3190 weatherMetricsTabSections weather_metrics_official_alerts_section
		wertebereiche_sprache wetter_metriken_laedt_keine_compare_klebeschicht wind_chill_kanal_mitnahme_speicherpfad
	`,
	'lib/components/shared/wetter-tab/__tests__': 'fixloop3_c1_svelte_proxy_klon s3a2794_teil4a_umzug_waechter vorlageName_render',
	'lib/components/trip-detail/__tests__': `
		tempo_fixloop4_3196 tempo_je_etappe_3197 tempo_je_etappe_3197_fixloop1 tempo_je_etappe_3197_fixloop4
		tempo_je_etappe_3197_mobil tempo_karte_3196 tempo_panel_3196_fixloop3 tempo_verdrahtung_3196_fixloop2
		trip_header_status_profil trip_hub_sprache trip_konflikt_schreibt_seitenstand_fort
		trip_mehrreiter_nach_412_kein_verlust trip_night_block_schalter_nutzlast trip_night_block_schalter_verdrahtung
		trip_python_skip_next_ohne_412 trip_reiter_nutzlast_nur_eigene_felder trip_reiter_roundtrip_jedes_feld
		trip_retry_adoption_schutz trip_retry_fehlerpfade_kein_verlust trip_retry_nach_reiterwechsel
		trip_retry_reiterwechsel_eingabe_bleibt trip_versand_reiter_ohne_dauer_keepalive weatherSaveGate
	`,
	'lib/components/trip-detail': 'bug_499_skala_label',
	'lib/components/trip-new/__tests__': 'standardwerte_payload_paritaet_trip tempo_je_etappe_3197_anlegen_verdrahtung trip_anlegen_sprache',
	'lib/i18n/__tests__': 'katalog_schluessel_haben_verwender keine_hartkodierten_nutzertexte reaktivitaet_waechter',
	'lib/stores/__tests__': 'saveStatus',
	'lib/utils/__tests__': 'report_slot_aktiv',
	'routes/_home/__tests__': 'home_hero_paritaet',
	'routes/gpx-upload/__tests__': 'gpx_upload_sprache',
	'routes/trips/[id]/__tests__': 'trip_hub_loeschen'
};

export const ROTE_LISTE: string[] = Object.entries(NAMEN).flatMap(([ordner, namen]) =>
	namen
		.trim()
		.split(/\s+/)
		.map((n) => `${ordner}/${n}.test.ts`)
);

/** Länge der eingefrorenen Liste (Vakuum-Schutz). */
export const ROTE_LISTE_ANZAHL = 161;
