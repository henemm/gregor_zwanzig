<script lang="ts">
	// AlertChannelPicker — Issue #1258 Scheibe S2: geteilter Kanal-Picker fuer
	// die Alarm-Zustellung (Telegram/SMS/E-Mail), getrennt vom Briefing-Kanal-
	// Picker (VTBriefingChannels). Fuer die Kanal-Zeile existiert im Svelte-Code
	// kein Pendant (Design-Molecule ChannelRow ist reines JSX) — daher hier neu
	// nach Design gebaut, unter Wiederverwendung der bestehenden Atome
	// Switch/Card/Eyebrow.
	//
	// Design: claude-code-handoff/current/jsx/corridor-editor.jsx:469-489,
	//   ChannelRow-Molecule molecules.jsx:177-230 (dense-Layout).
	// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-11)
	//
	// Ungewired in dieser Scheibe — keine Flaeche bindet diese Komponente ein.

	import { Eyebrow, Card, Switch } from '$lib/components/atoms';
	import {
		ALERT_CHANNEL_ORDER,
		NO_CHANNEL_WARNING,
		channelWarningNeeded,
		CHANNEL_THRESHOLD_LEVELS,
		CHANNEL_THRESHOLD_LABELS,
		type AlertChannelState,
		type AlertChannelThresholdState,
		type ChannelKind,
		type ChannelThreshold
	} from './alarme-tab/alertChannelState.ts';

	interface Props {
		channels: AlertChannelState;
		onToggle: (kind: ChannelKind) => void;
		targets?: Partial<Record<ChannelKind, string>>;
		dense?: boolean;
		// Issue #1461 S3b-2a/S3b-2b: beide Props optional -- ohne sie bleibt die
		// Zeile wie vor S3b-2a (statischer Beschreibungstext). Der Picker ist auf
		// vier Flaechen eingebettet (Trip-Alarm-Reiter, Vergleichs-Hub, beide
		// Compare-Anlege-Masken); seit S3b-2b zeigen und bedienen alle vier die
		// Stufen-Auswahl (kein Vergleichs-Zweig ohne eigene Wirkung mehr).
		thresholds?: AlertChannelThresholdState;
		onThresholdChange?: (kind: ChannelKind, level: ChannelThreshold) => void;
		// Issue #1745 A (D3): gesperrte Kanaele — Schluessel = Kanal, Wert =
		// Hinweistext. Die Zeile bleibt SICHTBAR, nur der Schalter ist gesperrt
		// (versteckt waere vorgespiegelte Abwesenheit statt ehrlicher Sperre).
		disabledChannels?: Partial<Record<ChannelKind, string>>;
	}
	let {
		channels,
		onToggle,
		targets,
		dense = false,
		thresholds,
		onThresholdChange,
		disabledChannels
	}: Props = $props();

	const CHANNEL_LABELS: Record<ChannelKind, string> = {
		telegram: 'Telegram',
		sms: 'SMS',
		// Issue #1745 A (D5): woertlich wie im Versand-Reiter.
		premium_sms: 'Premium-SMS (Garmin inReach)',
		email: 'Email'
	};
	const CHANNEL_SUB: Record<ChannelKind, string> = {
		telegram: 'sofortiger Push',
		sms: 'sofort · ≤ 140 Z.',
		premium_sms: 'Satellit · auch ohne Handynetz',
		email: 'optional · langsamer als Push'
	};

	const activeCount = $derived(ALERT_CHANNEL_ORDER.filter((k) => channels[k]).length);
	const warningNeeded = $derived(channelWarningNeeded(channels));

	// Factory-Pattern (Safari-Closure-Schutz, CLAUDE.md) — jede Zeile bekommt
	// ihren eigenen Handler statt einer gemeinsamen Closure ueber die Loop-Variable.
	function makeToggleHandler(kind: ChannelKind) {
		return function doToggle() {
			onToggle(kind);
		};
	}

	// Issue #1461 S3b-2a — AC-10: je Kanal-Zeile eine Stufen-Auswahl an der
	// Stelle, an der bisher nur statischer Beschreibungstext stand
	// (CHANNEL_SUB). Factory-Pattern analog makeToggleHandler.
	function makeThresholdHandler(kind: ChannelKind, level: ChannelThreshold) {
		return function doSelectThreshold() {
			onThresholdChange?.(kind, level);
		};
	}
</script>

<div data-testid="alert-channel-picker">
	<div class="acp-head">
		<Eyebrow style="margin: 0;">Alert-Kanäle</Eyebrow>
		<span
			class="mono acp-counter"
			class:warn={warningNeeded}
			data-testid="alert-channel-picker-warning"
		>
			{warningNeeded ? NO_CHANNEL_WARNING : `${activeCount} aktiv`}
		</span>
	</div>
	<p class="acp-lead">
		Alerts sind kurze Sofort-Meldungen — <strong>Telegram/SMS</strong> sind dafür ideal. Das geplante
		Briefing (die Tabelle) läuft davon getrennt weiter über seine eigenen Kanäle.
	</p>
	<Card padding={0}>
		<div class="acp-rows" style:padding={dense ? '2px 14px' : '4px 18px'}>
			{#each ALERT_CHANNEL_ORDER as kind, i (kind)}
				<div
					class="acp-row"
					class:last={i === ALERT_CHANNEL_ORDER.length - 1}
					data-testid="alert-channel-row-{kind}"
				>
					<span class="mono acp-kind">{CHANNEL_LABELS[kind]}</span>
					<div class="acp-target">
						<div class="mono acp-target-value">{targets?.[kind] ?? '—'}</div>
						{#if thresholds}
							<!-- Issue #1461 S3b-2a AC-10: Stufen-Auswahl statt statischem Text. -->
							<div
								class="acp-threshold"
								data-testid="alert-channel-threshold-{kind}"
								role="group"
								aria-label="Dringlichkeits-Schwelle {CHANNEL_LABELS[kind]}"
							>
								{#each CHANNEL_THRESHOLD_LEVELS as level (level)}
									<button
										type="button"
										class="acp-threshold-btn"
										class:active={thresholds[kind] === level}
										aria-pressed={thresholds[kind] === level}
										data-testid="alert-channel-threshold-{kind}-{level}"
										onclick={makeThresholdHandler(kind, level)}
									>
										{CHANNEL_THRESHOLD_LABELS[level]}
									</button>
								{/each}
							</div>
						{:else}
							<div class="acp-sub">{CHANNEL_SUB[kind]}</div>
						{/if}
						{#if disabledChannels?.[kind]}
							<!-- Issue #1745 A (D3): eine gesperrte Zeile ohne Begruendung waere
							     eine Sackgasse. -->
							<div class="acp-sub" data-testid="alert-channel-disabled-hint-{kind}">
								{disabledChannels[kind]}
							</div>
						{/if}
					</div>
					<div data-testid="alert-channel-toggle-{kind}">
						<Switch
							checked={channels[kind]}
							onchange={makeToggleHandler(kind)}
							disabled={!!disabledChannels?.[kind]}
							tone="good"
							size={dense ? 'lg' : 'md'}
							aria-label="{CHANNEL_LABELS[kind]} umschalten"
						/>
					</div>
				</div>
			{/each}
		</div>
	</Card>
</div>

<style>
	.acp-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 6px;
	}
	.acp-counter {
		font-size: 10px;
		color: var(--g-ink-3);
		letter-spacing: 0.03em;
	}
	.acp-counter.warn {
		color: var(--g-warning, var(--g-warn));
	}
	.acp-lead {
		font-size: 12.5px;
		color: var(--g-ink-3);
		line-height: 1.5;
		margin: 0 0 10px;
	}
	.acp-rows {
		display: flex;
		flex-direction: column;
	}
	.acp-row {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 0;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.acp-row.last {
		border-bottom: none;
	}
	.acp-kind {
		font-size: 10px;
		width: 60px;
		flex-shrink: 0;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--g-ink-3);
	}
	.acp-target {
		flex: 1;
		min-width: 0;
	}
	.acp-target-value {
		font-size: 12px;
		color: var(--g-ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.acp-sub {
		font-size: 10px;
		color: var(--g-ink-4);
		margin-top: 2px;
	}
	/* Issue #1461 S3b-2a AC-10: Stufen-Auswahl je Kanal-Zeile. */
	.acp-threshold {
		display: flex;
		gap: 4px;
		margin-top: 3px;
	}
	.acp-threshold-btn {
		font-size: 10px;
		padding: 2px 7px;
		border: 1px solid var(--g-rule-soft);
		border-radius: 999px;
		background: transparent;
		color: var(--g-ink-2, var(--g-ink-3));
		cursor: pointer;
	}
	.acp-threshold-btn.active {
		background: var(--g-accent, #2563eb);
		border-color: var(--g-accent, #2563eb);
		color: #ffffff;
	}
</style>
