<script lang="ts">
	// Step 4: Briefings & Kanaele (Epic #136 Sub-Spec #164, Issue #224).
	// Quelle: docs/specs/modules/epic_136_step4_briefings.md §7
	//         docs/specs/modules/issue_224_wizard_alert_rules_editor.md §3
	//
	// Drei Sektionen, jede in eigenem GCard mit Eyebrow-Ueberschrift:
	//   1. Kanaele     (4 ChannelToggles: email, signal, telegram, sms-disabled)
	//   2. Reports     (2 ReportRows: morning, evening)
	//   3. Alarmregeln (AlertRulesEditor — Issue #224)
	//
	// State: getContext('trip-wizard-state') — Channels/Reports mutieren
	// `wizard.briefings.{channels|reports}.*`; AlertRules sind direkt an
	// `wizard.alertRules` (Top-Level-State, $bindable).
	//
	// Save-Button kommt aus TripWizardShell, nicht hier (state.save()).

	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { GCard } from '$lib/components/ui/g-card';
	import type { WizardState, BriefingConfig } from '../wizardState.svelte';
	import ChannelToggle from './ChannelToggle.svelte';
	import ReportRow from './ReportRow.svelte';
	import { AlertRulesEditor } from '$lib/components/organisms';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Factory-Handler (CLAUDE.md Safari-Pattern) -------------------------

	function makeChannelHandler(channel: keyof BriefingConfig['channels']) {
		return function doToggleChannel(checked: boolean): void {
			wizard.briefings.channels[channel] = checked;
		};
	}

	function makeReportEnabledHandler(report: 'morning' | 'evening') {
		return function doToggleReport(enabled: boolean): void {
			wizard.briefings.reports[report].enabled = enabled;
		};
	}

	function makeReportTimeHandler(report: 'morning' | 'evening') {
		return function doSetReportTime(time: string): void {
			wizard.briefings.reports[report].time = time;
		};
	}

	// SMS-Channel ist disabled — Toggle hat einen No-op-Handler.
	function doNoopSmsToggle(_checked: boolean): void {
		// intentional no-op — SMS-Channel ist in der UI gesperrt (Spec §7, AC#5)
	}
</script>

<div data-testid="trip-wizard-step4-container" class="space-y-6 py-4">
	<!-- Sektion 1: Kanaele -->
	<section class="space-y-2">
		<Eyebrow class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]"
			>Kanäle</Eyebrow
		>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div data-testid="trip-wizard-step4-channels-list" class="space-y-3">
				<ChannelToggle
					label="E-Mail"
					checked={wizard.briefings.channels.email}
					onchange={makeChannelHandler('email')}
					testid="trip-wizard-step4-channel-email"
				/>
				<ChannelToggle
					label="Signal"
					checked={wizard.briefings.channels.signal}
					onchange={makeChannelHandler('signal')}
					testid="trip-wizard-step4-channel-signal"
				/>
				<ChannelToggle
					label="Telegram"
					checked={wizard.briefings.channels.telegram}
					onchange={makeChannelHandler('telegram')}
					testid="trip-wizard-step4-channel-telegram"
				/>
				<ChannelToggle
					label="SMS"
					checked={false}
					disabled
					hint="demnächst verfügbar"
					onchange={doNoopSmsToggle}
					testid="trip-wizard-step4-channel-sms"
				/>
			</div>
		</GCard>
	</section>

	<!-- Sektion 2: Reports -->
	<section class="space-y-2">
		<Eyebrow class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]"
			>Reports</Eyebrow
		>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div data-testid="trip-wizard-step4-reports-list" class="space-y-3">
				<ReportRow
					label="Morgen-Briefing"
					enabled={wizard.briefings.reports.morning.enabled}
					time={wizard.briefings.reports.morning.time}
					onEnabledChange={makeReportEnabledHandler('morning')}
					onTimeChange={makeReportTimeHandler('morning')}
					testidToggle="trip-wizard-step4-report-morning-toggle"
					testidTime="trip-wizard-step4-report-morning-time"
				/>
				<ReportRow
					label="Abend-Briefing"
					enabled={wizard.briefings.reports.evening.enabled}
					time={wizard.briefings.reports.evening.time}
					onEnabledChange={makeReportEnabledHandler('evening')}
					onTimeChange={makeReportTimeHandler('evening')}
					testidToggle="trip-wizard-step4-report-evening-toggle"
					testidTime="trip-wizard-step4-report-evening-time"
				/>
			</div>
		</GCard>
	</section>

	<!-- Sektion 3: Alarmregeln (Issue #224 — AlertRulesEditor) -->
	<section class="space-y-2">
		<Eyebrow class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]"
			>Alarmregeln</Eyebrow
		>
		<AlertRulesEditor bind:rules={wizard.alertRules} />
	</section>
</div>
