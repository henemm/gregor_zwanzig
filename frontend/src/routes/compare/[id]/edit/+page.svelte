<script lang="ts">
	// Issue #679 — Compare-Edit-Route: CompareWizard → CompareEditor mode="edit".
	// Spec: docs/specs/modules/issue_679_compare_editor_edit.md
	// Löst: (1) save() traf /api/subscriptions statt /api/compare/presets,
	//        (2) empfaenger wurde beim Speichern gelöscht (fehlender Round-Trip-Spread).
	//
	// State-Initialisierung aus data.preset.* unverändert.
	// data.preset wird zusätzlich als Prop an CompareEditor gegeben (Round-Trip-Spread + Status-Dot).

	import { setContext } from 'svelte';
	import { goto, beforeNavigate } from '$app/navigation';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareEditor from '$lib/components/compare/CompareEditor.svelte';
	import { rehydrateActiveMetrics } from '$lib/components/compare/compareEditorLoad';
	import type { IdealRange } from '$lib/components/compare/compareMetricDefs';
	import type { ActivityProfile, ChannelLayouts } from '$lib/types';

	let { data } = $props();

	// Issue #1261 (b): Flush ausstehender Auto-Saves vor Navigation, analog
	// routes/trips/[id]/+page.svelte:25-34. compareSaveCtl lebt in CompareEditor
	// (eigene Instanz pro Editor, kein Singleton, Issue #758 AC-6) — via
	// bind:this + exportiertem Getter erreichbar gemacht.
	// Kein $state() hier (bewusst): diese Datei hat bereits eine lokale
	// Bindung `state` (CompareWizardState, s.u.) — `$state()` daneben wuerde
	// Sveltes Store-Autosubscription-Heuristik faelschlich triggern
	// (store_rune_conflict). editorRef wird nur imperativ in beforeNavigate
	// gelesen, keine reaktive Nutzung im Markup noetig.
	let editorRef: ReturnType<typeof CompareEditor> | undefined;
	beforeNavigate(({ cancel, to, willUnload }) => {
		if (willUnload) return; // Browser-Navigation, kein Flush möglich
		const saveCtl = editorRef?.getCompareSaveController();
		if (saveCtl?.hasPending) {
			cancel();
			const targetUrl = to?.url?.href ?? null;
			void saveCtl.flush().then(() => {
				if (targetUrl) void goto(targetUrl);
			});
		}
	});

	const state = new CompareWizardState();
	state.isEditMode = true;
	state.subscriptionId = data.preset.id;
	state.name = data.preset.name ?? '';
	state.activityProfile = (data.preset.profil as ActivityProfile | null) ?? null;
	state.pickedIds = data.preset.location_ids ?? [];
	state.subscriptionEnabled = true; // ComparePreset hat kein enabled-Feld
	state.existingDisplayConfig = (data.preset.display_config as Record<string, unknown>) ?? {};
	state.region = (state.existingDisplayConfig.region as string) ?? '';
	state.idealRanges =
		(state.existingDisplayConfig.ideal_ranges as Record<string, IdealRange>) ?? {};
	// Issue #1231 Slice 4: Korridore (Top-Level-Feld auf ComparePreset).
	state.corridors = data.preset.corridors ?? [];

	// Versand-Felder aus preset mappen
	state.schedule = data.preset.schedule ?? 'daily';
	state.weekday = data.preset.weekday ?? 0;
	state.timeWindowStart = data.preset.hour_from ?? 9;
	state.timeWindowEnd = data.preset.hour_to ?? 16;
	state.forecastHours = data.preset.forecast_hours ?? 48; // Issue #764
	state.officialAlertsEnabled = data.preset.official_alerts_enabled ?? true; // Issue #1040
	state.radarAlertEnabled = data.preset.radar_alert_enabled ?? false; // Issue #1041 Slice 2 (Default AUS)
	state.hourlyEnabled = data.preset.hourly_enabled ?? true; // Issue #1107
	// Issue #1216 Slice 2b: Trigger Default AN, Kanäle Default AUS.
	state.officialAlertTriggersEnabled = data.preset.official_alert_triggers_enabled ?? true;
	state.sendTelegram = data.preset.send_telegram ?? false;
	state.sendSms = data.preset.send_sms ?? false;
	// Issue #1258 S4 (AC-27): Hydration des scharfen Felds. Default false =
	// F1-Neuanlage-Default (analog Trip-Hydration), sollte bei Bestand aber
	// immer gesetzt sein (S1-Migration).
	state.officialWarningsEnabled = data.preset.official_warnings?.enabled ?? false;
	state.topN = (state.existingDisplayConfig.top_n as number) ?? 3; // Issue #1104

	// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + editierbare Laufzeit.
	// Defaults identisch zur Go-Load-Migration (Scheibe 2a).
	state.morningEnabled = data.preset.morning_enabled ?? true;
	state.morningTime = (data.preset.morning_time ?? '06:00').slice(0, 5);
	state.eveningEnabled = data.preset.evening_enabled ?? false;
	state.eveningTime = (data.preset.evening_time ?? '18:00').slice(0, 5);
	state.endDate = data.preset.end_date ?? null;

	// Issue #1170 — Alarm-Konfiguration (Epic #1095 Scheibe 3/3).
	state.metricAlertLevels =
		(state.existingDisplayConfig.metric_alert_levels as Record<string, string>) ?? {};
	// Issue #1260 S5 — Telegram-Kurzstil aus display_config (Default "rich").
	state.telegramStyle =
		(state.existingDisplayConfig.telegram_style as 'rich' | 'kurzform') ?? 'rich';
	state.alertCooldownMinutes = data.preset.alert_cooldown_minutes ?? undefined;
	state.alertQuietFrom = data.preset.alert_quiet_from ?? undefined;
	state.alertQuietTo = data.preset.alert_quiet_to ?? undefined;

	// Kanal-Layouts aus display_config
	const savedLayouts = state.existingDisplayConfig.channel_layouts as
		| ChannelLayouts
		| undefined;
	if (savedLayouts) state.channelLayouts = savedLayouts;

	// Issue #680: Slice 3 — active_metrics aus display_config wiederherstellen (AC-10)
	// Issue #1191: Ein vorhandenes leeres [] ("alles abgewählt") ist bewusste
	// Nutzerwahl und muss erhalten bleiben — NICHT auf Profil-Defaults zurückspringen.
	const savedActiveMetrics = state.existingDisplayConfig.active_metrics as string[] | undefined;
	const rehydrated = rehydrateActiveMetrics(savedActiveMetrics);
	if (rehydrated) {
		state.activeMetricKeys = rehydrated.activeMetricKeys;
		state.metricsManuallyEdited = rehydrated.metricsManuallyEdited;
	}

	// Issue #1106: Slice C — hourly_metrics aus display_config wiederherstellen
	const savedHourlyMetrics = state.existingDisplayConfig.hourly_metrics as string[] | undefined;
	if (savedHourlyMetrics && savedHourlyMetrics.length > 0) {
		state.hourlyMetricKeys = savedHourlyMetrics;
	}

	setContext('compare-wizard-state', state);
	setContext('compare-wizard-profile', data.profile ?? null);
</script>

<CompareEditor mode="edit" locations={data.locations} preset={data.preset} bind:this={editorRef} />
