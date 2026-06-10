<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Abschnitt 4 Kanäle.
	// 1:1 nach WM2_Kanaele aus screen-trip-edit-v2-weather.jsx.
	// Kein Signal (#610). Telegram-Budget=8. Bei Telegram an + >8 Spalten:
	// Kurzform-Toggle (telegram_kurzform).
	import { Switch } from '$lib/components/atoms';
	import { CHANNEL_COL_BUDGET } from './metricsEditor.ts';

	interface ChannelConfig {
		email: boolean;
		telegram: boolean;
		sms: boolean;
	}

	interface Props {
		channels: ChannelConfig;
		primaryCount: number;
		telegramKurzform: boolean;
		onChange: (updated: ChannelConfig) => void;
		onKurzformChange: (v: boolean) => void;
		availability?: { email: boolean; telegram: boolean; sms: boolean };
	}

	let { channels, primaryCount, telegramKurzform, onChange, onKurzformChange, availability }: Props = $props();

	const WM2_CHANNELS = [
		{ id: 'email' as const,    label: 'Email',    glyph: '✉', max: 99,  note: 'alle Spalten · kein Limit' },
		{ id: 'telegram' as const, label: 'Telegram', glyph: '✈', max: CHANNEL_COL_BUDGET.telegram, note: `max ${CHANNEL_COL_BUDGET.telegram} Spalten` },
		{ id: 'sms' as const,      label: 'SMS',      glyph: '✱', max: 0,   note: 'kein Raster · 140 Zeichen' },
	] as const;

	type ChannelId = 'email' | 'telegram' | 'sms';

	function toggle(id: ChannelId) {
		onChange({ ...channels, [id]: !channels[id] });
	}
</script>

<div class="kanaele" data-testid="wm2-kanaele">
	{#each WM2_CHANNELS as ch}
		{@const on = channels[ch.id]}
		<div class="ch-card" class:on data-channel={ch.id}>
			<button
				type="button"
				class="ch-row"
				onclick={() => toggle(ch.id)}
				aria-pressed={on}
				disabled={!(availability?.[ch.id] ?? true)}
			>
				<span class="ch-glyph mono" class:active={on} aria-hidden="true">{ch.glyph}</span>
				<div class="ch-info">
					<div class="ch-label" class:on>{ch.label}</div>
					<div class="ch-note mono">{ch.note}</div>
				</div>
				<Switch
					checked={on}
					size="md"
					tone="good"
					aria-label="{ch.label} aktivieren"
					onchange={(v) => { if (v !== on) toggle(ch.id); }}
				/>
			</button>
			{#if !(availability?.[ch.id] ?? true)}
				<div class="ch-hint" data-testid="channel-{ch.id}-hint">
					{ch.label} nicht konfiguriert —
					<a href="/account">im Account einrichten</a>
				</div>
			{/if}
			{#if ch.id === 'telegram' && on && (availability?.telegram ?? true) && primaryCount > CHANNEL_COL_BUDGET.telegram}
				<div class="kurzform-row">
					<Switch
						checked={telegramKurzform}
						size="md"
						tone="good"
						aria-label="Tages-Max für übrige Metriken"
						onchange={onKurzformChange}
					/>
					<div class="kurzform-info" role="button" tabindex="0" onclick={() => onKurzformChange(!telegramKurzform)} onkeydown={(e) => e.key === ' ' && onKurzformChange(!telegramKurzform)}>
						<div class="kurzform-title">Tages-Max für übrige Metriken</div>
						<div class="kurzform-desc">
							{primaryCount - CHANNEL_COL_BUDGET.telegram} Metriken passen nicht in die Tabelle — als kompakte Tageszusammenfassung anhängen
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/each}
	<div class="footnote">
		Aktivierte Kanäle erscheinen auch im <strong>Briefing-Zeitplan</strong> und als Standard in den <strong>Alerts</strong>.
	</div>
</div>

<style>
	.kanaele {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.ch-card {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card-alt);
		overflow: hidden;
		transition: border-color 120ms, background 120ms;
	}
	.ch-card.on {
		border-color: var(--g-ink);
		background: var(--g-card);
	}
	.ch-row {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 14px 16px;
		cursor: pointer;
		width: 100%;
		background: none;
		border: none;
		font-family: inherit;
		text-align: left;
	}
	.ch-glyph {
		font-size: 16px;
		width: 22px;
		text-align: center;
		color: var(--g-ink-4);
		flex-shrink: 0;
	}
	.ch-glyph.active {
		color: var(--g-ink);
	}
	.ch-info {
		flex: 1;
		min-width: 0;
	}
	.ch-label {
		font-size: 14px;
		font-weight: 600;
		color: var(--g-ink-3);
		transition: color 120ms;
	}
	.ch-label.on {
		color: var(--g-ink);
	}
	.ch-note {
		font-size: 11px;
		color: var(--g-ink-4);
		margin-top: 1px;
	}
	.kurzform-row {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		padding: 10px 16px 14px 52px;
		border-top: 1px solid var(--g-rule-soft);
	}
	.kurzform-info {
		cursor: pointer;
	}
	.kurzform-title {
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.kurzform-desc {
		font-size: 12px;
		color: var(--g-ink-3);
		margin-top: 2px;
		line-height: 1.45;
	}
	.ch-hint {
		font-size: 12px;
		color: var(--g-ink-3);
		padding: 0 16px 12px 52px;
		line-height: 1.45;
	}
	.ch-hint a {
		color: var(--g-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.ch-row:disabled {
		cursor: default;
		opacity: 0.6;
	}
	.footnote {
		font-size: 12px;
		color: var(--g-ink-3);
		line-height: 1.5;
		padding-left: 2px;
	}
</style>
