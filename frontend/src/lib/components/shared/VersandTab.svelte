<script lang="ts">
	// VersandTab — Issue #1232 Scheibe 1: geteilter Versand-Organism
	// (Epic #29/#1230, Phase 4 Editor-Konsolidierung).
	//
	// EIN Organism für Trip-Editor (context="route") und Compare-Editor
	// (context="vergleich", folgt Scheibe 2 — KL-3). Buendelt alles was
	// rausgeht: Briefing-Kanaele, Briefing-Zeitplan, Laufzeit und die
	// komplette Alert-Zustellung (bisher im Alerts-Tab).
	//
	// Design-Quelle (1:1): claude-code-handoff/current/jsx/versand-tab.jsx
	// Spec: docs/specs/modules/versand_tab_route.md

	import { onMount, untrack, type Snippet } from 'svelte';
	import { api } from '$lib/api.js';
	import { toHHMMSS } from '$lib/utils/time';
	import type { Trip, ReportConfig } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import VTBriefingChannels from './versand-tab/VTBriefingChannels.svelte';
	import VTSchedulePlan from './versand-tab/VTSchedulePlan.svelte';
	import VTLaufzeitRoute from './versand-tab/VTLaufzeitRoute.svelte';
	import VTLaufzeitVergleich from './versand-tab/VTLaufzeitVergleich.svelte';
	// Issue #1738 Fix-Loop 1 (F001/F002): die Read-Modify-Write-Regel des
	// report_config-Blobs steht als reine, pruefbare Funktion neben beiden
	// Schreibern statt zweimal im jeweiligen Effect-Rumpf.
	import { mergeReportConfig } from './versand-tab/mergeReportConfig.ts';
	// Issue #1258 Scheibe S4 (E5): die komplette Alert-Zustellungs-Sektion des
	// vergleich-Zweigs (Cooldown-/Quiet-Karten + Beispiel-Warnung) zog atomar
	// in AlarmeTab.svelte um (Radar/Metrik-Level-Tabelle waren dort nie).
	// AlertCooldownCard/AlertQuietHoursCard/VTAlertSample/Eyebrow werden daher
	// hier nicht mehr importiert.

	interface Props {
		context?: 'route' | 'vergleich';
		trip?: Trip;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		/** report_config-Blob — bind:reportConfig durchgereicht an den Parent (BriefingScheduleTab). Nur route. */
		reportConfig?: ReportConfig;
		/** Issue #736: display_config.channels-Sync bei Kanal-Toggle (Parent-Callback). Nur route. */
		onChannelChange?: (channel: 'email' | 'telegram' | 'sms', value: boolean) => void;
		/** Tab-Wechsel (analog HubOverview onJump) — "Etappen öffnen →" springt in 'stages'. Nur route. */
		onJump?: (tab: string) => void;
		/** Issue #1232 Scheibe 2b: geteilter Compare-Wizard-State (context="vergleich").
		 * KEIN Self-Save — alle Controls binden direkt an wiz.*, Persistenz bleibt
		 * zentral in CompareEditor.handleSave()/wiz.saveNewPreset() (Doppel-Mount
		 * Desktop+Mobile, Create ohne Preset-ID). */
		wiz?: CompareWizardState;
		/** Issue #1232 Scheibe 2b: Create-Aktivierungs-Banner (1:1 JSX-Slot), nur vergleich. */
		activation?: Snippet;
	}
	let {
		context = 'route',
		trip,
		onTripUpdate,
		saveController,
		reportConfig = $bindable(),
		onChannelChange,
		onJump,
		wiz,
		activation
	}: Props = $props();

	// ── Sektion 1+2: Briefing-Kanäle + Zeitplan (report_config) ────────────────
	let originalReportConfig: ReportConfig = {};
	let morning_enabled = $state(true);
	let evening_enabled = $state(true);
	let morning_time = $state('07:00');
	let evening_time = $state('18:00');
	let multi_day_trend_morning = $state(false);
	let multi_day_trend_evening = $state(false);
	// Issue #1717 S3: die vier Briefing-Kanal-Flags stehen schon BEIM ERZEUGEN
	// aus report_config (untrack, Muster EditReportConfigSection.svelte:76) und
	// nicht erst in onMount. Zwei Gruende: der erste Rahmen zeigte sonst
	// "E-Mail an" auch fuer einen Trip, der gar keine E-Mail schickt — und der
	// Zeitplan-Leerzustand unten (activeChannelCount) waere ohne diese
	// Initialisierung beim Rendern gar nicht erreichbar, also auch nicht
	// pruefbar. Die Zuweisungen in onMount bleiben (Nachladen), Semantik
	// identisch: E-Mail Default an, alles andere Default aus.
	let send_email = $state(untrack(() => reportConfig?.send_email !== false));
	let send_telegram = $state(untrack(() => reportConfig?.send_telegram === true));
	let send_sms = $state(untrack(() => reportConfig?.send_sms === true));
	// Issue #1717 S3: vierter Briefing-Kanal (Premium-SMS, Garmin inReach).
	// Ohne State/Hydration/Write-Back hier bliebe ein Klick in
	// VTBriefingChannels auf /trips/[id] folgenlos — dies ist die
	// Persistenz-Schicht dieser Seite (bind:reportConfig aus
	// BriefingScheduleTab). Nur route: im vergleich-Zweig ist Premium-SMS kein
	// Kanal (ADR-0049).
	let send_premium_sms = $state(untrack(() => reportConfig?.send_premium_sms === true));
	// Issue #1260 S5: Trip-Kurzstil-Schalter (report_config.telegram_style).
	// EIN Trip-Feld regelt Briefing UND Alarme — der Schalter erscheint einmal
	// hier im Versand-Tab.
	let telegram_style = $state<'rich' | 'kurzform'>('rich');

	onMount(() => {
		if (reportConfig) {
			originalReportConfig = { ...reportConfig };
			const c = originalReportConfig;
			const globallyEnabled = typeof c.enabled === 'boolean' ? c.enabled : true;
			morning_enabled =
				typeof c.morning_enabled === 'boolean'
					? c.morning_enabled
					: globallyEnabled && typeof c.morning_time === 'string';
			evening_enabled =
				typeof c.evening_enabled === 'boolean'
					? c.evening_enabled
					: globallyEnabled && typeof c.evening_time === 'string';
			if (typeof c.morning_time === 'string') morning_time = c.morning_time.slice(0, 5);
			if (typeof c.evening_time === 'string') evening_time = c.evening_time.slice(0, 5);
			if (typeof c.send_email === 'boolean') send_email = c.send_email;
			if (typeof c.send_telegram === 'boolean') send_telegram = c.send_telegram;
			if (typeof c.send_sms === 'boolean') send_sms = c.send_sms;
			if (typeof c.send_premium_sms === 'boolean') send_premium_sms = c.send_premium_sms;
			if (c.telegram_style === 'kurzform' || c.telegram_style === 'rich') {
				telegram_style = c.telegram_style;
			}
			if (typeof c.multi_day_trend_morning === 'boolean') {
				multi_day_trend_morning = c.multi_day_trend_morning;
			} else if (Array.isArray(c.multi_day_trend_reports)) {
				multi_day_trend_morning = c.multi_day_trend_reports.includes('morning');
			}
			if (typeof c.multi_day_trend_evening === 'boolean') {
				multi_day_trend_evening = c.multi_day_trend_evening;
			} else if (Array.isArray(c.multi_day_trend_reports)) {
				multi_day_trend_evening = c.multi_day_trend_reports.includes('evening');
			}
		}
	});

	$effect(() => {
		const multi_day_trend_reports: string[] = [];
		if (multi_day_trend_morning) multi_day_trend_reports.push('morning');
		if (multi_day_trend_evening) multi_day_trend_reports.push('evening');
		// Issue #1738: Read-Modify-Write ueber den geteilten Helfer, Basis ist der
		// LEBENDE Blob (untrack -> kein Selbst-Trigger) und nicht mehr nur der
		// Mount-Schnappschuss. Seit /trips/new diese Komponente neben
		// EditReportConfigSection auf dasselbe bind:reportConfig mountet, wuerde
		// eine Zuweisung aus dem veralteten Schnappschuss jede Mail-Inhalt-
		// Einstellung des Nachbarn (email_format, show_outlook, ...) und jedes
		// unbekannte Bestandsfeld (change_threshold_*) still loeschen.
		// originalReportConfig bleibt Rueckfall fuer den ersten Lauf vor onMount.
		const merged = mergeReportConfig({
			snapshot: originalReportConfig as Record<string, unknown>,
			live: untrack(() => reportConfig) as Record<string, unknown> | undefined,
			own: {
				enabled: morning_enabled || evening_enabled,
				morning_enabled,
				evening_enabled,
				morning_time: toHHMMSS(morning_time),
				evening_time: toHHMMSS(evening_time),
				send_email,
				send_telegram,
				send_sms,
				// Issue #1717 S3 — derselbe Write-Back-Pfad wie die drei darueber.
				send_premium_sms,
				telegram_style,
				multi_day_trend_morning,
				multi_day_trend_evening,
				multi_day_trend_reports
			}
		});
		reportConfig = merged as ReportConfig;
	});

	// Issue #1717 S3: Premium-SMS zaehlt mit. Wer NUR Premium-SMS einschaltet,
	// bekommt ein echtes Briefing — ein Leerzustand "Kein Kanal aktiv" waere
	// dann eine Anzeige, die der Wirklichkeit widerspricht (und sie sperrt die
	// Zeitplan-Optionen weg, VTSchedulePlan.svelte:77). Dieselbe Zaehlung steht
	// in EditReportConfigSection.svelte (hasActiveChannel, /trips/new); beide
	// Fassungen werden im selben Testfall gegeneinander gemessen
	// (versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts).
	const activeChannelCount = $derived(
		[send_email, send_telegram, send_sms, send_premium_sms].filter(Boolean).length
	);

	// Issue #1232 Scheibe 2b: vergleich-Zweig — Kanal-Zähler direkt aus wiz.*
	// (kein lokaler $state, kein Self-Save).
	const vergleichActiveChannelCount = $derived(
		wiz ? [wiz.sendEmail, wiz.sendTelegram, wiz.sendSms].filter(Boolean).length : 0
	);

	// Factory-Pattern (Safari-Closure-Schutz, CLAUDE.md).
	function makeChannelChangeHandler(channel: 'email' | 'telegram' | 'sms') {
		return function doChange(e: Event) {
			const v = (e.target as HTMLInputElement).checked;
			if (channel === 'email') send_email = v;
			else if (channel === 'telegram') send_telegram = v;
			else send_sms = v;
			onChannelChange?.(channel, v);
		};
	}
	// Issue #1717 S3: eigener Factory-Handler statt Erweiterung von
	// makeChannelChangeHandler — dessen onChannelChange-Rueckruf synchronisiert
	// display_config.channels (#736), und das kennt nur die drei Wetter-Kanaele.
	// Premium-SMS dort mitzumelden waere ein Feld, das der Empfaenger nicht hat.
	function makePremiumSmsChangeHandler() {
		return function doChange(e: Event) {
			send_premium_sms = (e.target as HTMLInputElement).checked;
		};
	}
	// Issue #1232 Scheibe 2b: vergleich-Zweig — schreibt direkt in wiz.* statt
	// in lokale $state-Variablen (kein Self-Save, siehe Modul-Kommentar oben).
	function makeWizChannelHandler(field: 'sendEmail' | 'sendTelegram' | 'sendSms') {
		return function doChange(e: Event) {
			if (!wiz) return;
			wiz[field] = (e.target as HTMLInputElement).checked;
		};
	}
	function makeToggleHandler(setter: (v: boolean) => void) {
		return function doToggle(e: Event) {
			setter((e.target as HTMLInputElement).checked);
		};
	}
	function makeTimeHandler(setter: (v: string) => void) {
		return function doSetTime(e: Event) {
			setter((e.target as HTMLInputElement).value);
		};
	}
	// ── Sektion 3: Laufzeit (route = read-only aus Etappen) ────────────────────
	// t optional: im vergleich-Zweig wird trip nie gesetzt (Laufzeit-Sektion
	// dort ist VTLaufzeitVergleich, nicht VTLaufzeitRoute) — computeTripEnd
	// wird nur fuer den route-Zweig ausgewertet, defensiv trotzdem null-sicher.
	function computeTripEnd(t: Trip | undefined): string | null {
		if (!t) return null;
		const dates = (t.stages ?? [])
			.map((s) => s.date)
			.filter((d): d is string => !!d)
			.slice()
			.sort();
		if (dates.length === 0) return null;
		const clean = dates[dates.length - 1].split('T')[0];
		const [y, m, d] = clean.split('-');
		if (!y || !m || !d) return null;
		return `${d}.${m}.${y}`;
	}
	const tripEnd = $derived(computeTripEnd(trip));

	function handleOpenStages() {
		onJump?.('stages');
	}

	// Issue #1258 Scheibe S3 (D5): die komplette Alert-Zustellungs-Sektion des
	// route-Zweigs (officialAlertsEnabled/-Triggers, Cooldown, Stille Stunden,
	// Beispiel-Warnung + der EINE konsolidierte $effect dafür) zog atomar in
	// AlarmeScheduleTab.svelte/AlarmeTab.svelte um (kein Zwischenzustand mit
	// zwei Schreibpfaden auf dieselben Trip-Felder, F002-Race-Lektion). Der
	// vergleich-Zweig unten ist unverändert (eigene wiz.*-Bindung, kein
	// Self-Save, S4-Thema).
</script>

{#if context === 'route'}
	<div class="versand-tab" data-testid="versand-tab">
		<VTBriefingChannels
			{context}
			channels={{
				email: send_email,
				telegram: send_telegram,
				sms: send_sms,
				premium_sms: send_premium_sms
			}}
			onEmailChange={makeChannelChangeHandler('email')}
			onTelegramChange={makeChannelChangeHandler('telegram')}
			onSmsChange={makeChannelChangeHandler('sms')}
			telegramStyle={telegram_style}
			onTelegramStyleChange={(s) => (telegram_style = s)}
			onPremiumSmsChange={makePremiumSmsChangeHandler()}
		/>

		<VTSchedulePlan
			hasActiveChannel={activeChannelCount > 0}
			{morning_enabled}
			{morning_time}
			{evening_enabled}
			{evening_time}
			{multi_day_trend_morning}
			{multi_day_trend_evening}
			onMorningToggle={makeToggleHandler((v) => (morning_enabled = v))}
			onEveningToggle={makeToggleHandler((v) => (evening_enabled = v))}
			onMorningTime={makeTimeHandler((v) => (morning_time = v))}
			onEveningTime={makeTimeHandler((v) => (evening_time = v))}
			onTrendMorningToggle={makeToggleHandler((v) => (multi_day_trend_morning = v))}
			onTrendEveningToggle={makeToggleHandler((v) => (multi_day_trend_evening = v))}
		/>

		<VTLaufzeitRoute {tripEnd} onOpenStages={handleOpenStages} />
	</div>
{:else if context === 'vergleich'}
	<div class="versand-tab" data-testid="versand-tab">
		<VTBriefingChannels
			{context}
			channels={{
				email: wiz?.sendEmail ?? false,
				telegram: wiz?.sendTelegram ?? false,
				sms: wiz?.sendSms ?? false
			}}
			onEmailChange={makeWizChannelHandler('sendEmail')}
			onTelegramChange={makeWizChannelHandler('sendTelegram')}
			onSmsChange={makeWizChannelHandler('sendSms')}
			emailTestid="compare-step5-channel-email"
			telegramTestid="compare-step5-channel-telegram"
			smsTestid="compare-step5-channel-sms"
		/>

		<VTSchedulePlan
			context="vergleich"
			hasActiveChannel={vergleichActiveChannelCount > 0}
			morning_enabled={wiz?.morningEnabled ?? true}
			morning_time={wiz?.morningTime ?? '07:00'}
			evening_enabled={wiz?.eveningEnabled ?? false}
			evening_time={wiz?.eveningTime ?? '18:00'}
			onMorningToggle={makeToggleHandler((v) => {
				if (wiz) wiz.morningEnabled = v;
			})}
			onEveningToggle={makeToggleHandler((v) => {
				if (wiz) wiz.eveningEnabled = v;
			})}
			onMorningTime={makeTimeHandler((v) => {
				if (wiz) wiz.morningTime = v;
			})}
			onEveningTime={makeTimeHandler((v) => {
				if (wiz) wiz.eveningTime = v;
			})}
		/>

		<VTLaufzeitVergleich
			value={wiz?.endDate ?? null}
			onChange={(v) => {
				if (wiz) wiz.endDate = v;
			}}
		/>

		<!-- Issue #1258 Scheibe S4 (E5, AC-18): die Alert-Zustellungs-Sektion
		     (Cooldown, Stille Stunden, Beispiel-Warnung) rendert seither
		     ausschließlich der Alarme-Tab, nicht mehr hier. -->

		{#if activation}
			<div class="vt-activation-slot">{@render activation()}</div>
		{/if}
	</div>
{/if}

<style>
	.versand-tab {
		position: relative;
		padding: 28px 40px 60px;
		display: flex;
		flex-direction: column;
		gap: 30px;
		max-width: 900px;
	}
	@media (max-width: 899px) {
		.versand-tab {
			padding: 20px 16px 48px;
			gap: 22px;
		}
	}
</style>
