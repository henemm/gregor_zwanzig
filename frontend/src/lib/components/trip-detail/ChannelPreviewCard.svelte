<script lang="ts">
	// Issue #496 — Konsequenz-Kachel (Schicht 1) der "Pro Kanal"-Vorschau.
	// Statt einer Mini-Tabelle pro Karte zeigen die 4 Kacheln nun NUR die
	// Konsequenz der aktuellen Konfiguration je Kanal: "wie viele rutschen
	// raus?" Per Klick aktiviert der Nutzer Schicht 2 (Fidelity-Vorschau).
	import { applyChannel, type MetricEntry } from './metricsEditor.ts';

	interface Props {
		channelId: 'email' | 'telegram' | 'signal' | 'sms';
		label: string;
		glyph: string;
		maxCols: number;
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		active: boolean;
		onSelect: () => void;
	}
	let {
		channelId, label, glyph, maxCols, primary, secondary,
		metricById, active, onSelect,
	}: Props = $props();

	// SMS-Token-Tabelle (entscheidungskritische Metriken) — gespiegelt aus
	// ChannelFidelitySMS.svelte. Wird hier nur fuer den Zaehler verwendet.
	const SMS_TOK: Record<string, string> = {
		temperature: 'N8 D11',
		precipitation: 'R3.2',
		rain_probability: 'PR53%@12',
		wind: 'W12@11(24@13)',
		gust: 'G25@12(43@14)',
		thunder: 'TH5%@12',
	};
	const SMS_PREFIX = 'KHW03:';
	const SMS_TAIL = 'Z:WATCH:2447';
	const SMS_MAX = 140;

	function smsCounters(prim: string[], sec: string[]) {
		const order = [...prim, ...sec];
		const carried: string[] = [];
		let tokens: string[] = [];
		let dropped = 0;
		const lenWith = (toks: string[]) =>
			`${SMS_PREFIX} ${[...toks, SMS_TAIL].join(' ')}`.length;
		for (const id of order) {
			const tok = SMS_TOK[id];
			if (!tok) { dropped++; continue; }
			if (lenWith([...tokens, tok]) > SMS_MAX) { dropped++; continue; }
			tokens.push(tok);
			carried.push(id);
		}
		return { carried: carried.length, dropped, total: order.length };
	}

	const isSMS = $derived(channelId === 'sms');

	// Spaltenbasierte Kanäle (Email/Telegram/Signal): applyChannel teilt
	// primary in inTable (passt rein) + überzählige primary werden in
	// "detail" eingereiht. Anzahl der Demoteten = layout.demoted (number).
	const layout = $derived(applyChannel(primary, secondary, maxCols));
	const smsCount = $derived(smsCounters(primary, secondary));

	const bigNum = $derived(
		isSMS ? smsCount.carried : layout.inTable.length,
	);
	const bigSub = $derived(
		isSMS
			? `/ ${smsCount.total} als Code`
			: maxCols === Infinity
				? 'Spalten'
				: `/ ${maxCols} Spalten`,
	);
	const tone = $derived(
		isSMS
			? smsCount.dropped > 0 ? 'warn' : 'ok'
			: layout.demoted > 0 ? 'warn' : 'ok',
	);
	const statusText = $derived(
		isSMS
			? smsCount.dropped > 0
				? `${smsCount.dropped} ${smsCount.dropped === 1 ? 'fällt' : 'fallen'} weg`
				: 'alle haben Code'
			: layout.demoted > 0
				? `${layout.demoted} ${layout.demoted === 1 ? 'rutscht' : 'rutschen'}`
				: 'alle als Spalte',
	);
	// "Detail-Zeile" (in Schicht 2): bei Spalten-Kanaelen = overflow + secondary,
	// bei SMS = alle die keinen Code haben oder ueber Limit fallen.
	const detailCount = $derived(
		isSMS ? smsCount.dropped : layout.demoted + secondary.length,
	);
</script>

<button
	type="button"
	class="card"
	class:active
	class:warn={tone === 'warn'}
	data-testid="channel-consequence-{channelId}"
	aria-pressed={active}
	onclick={onSelect}
>
	<div class="head">
		<span class="glyph" aria-hidden="true">{glyph}</span>
		<span class="label">{label}</span>
		<span class="dot" class:dot-warn={tone === 'warn'} aria-hidden="true"></span>
	</div>

	<div class="metric">
		<span class="big mono">{bigNum}</span>
		<span class="sub mono">{bigSub}</span>
	</div>

	<div class="status">
		<span class="pill mono" class:pill-warn={tone === 'warn'}>{statusText}</span>
		{#if detailCount > 0}
			<span class="detail-count mono">+{detailCount} Detail</span>
		{/if}
	</div>
</button>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
		padding: var(--g-s-3);
		border: 1px solid var(--g-rule-soft);
		border-left: 3px solid transparent;
		border-radius: var(--g-radius-sm);
		background: transparent;
		text-align: left;
		cursor: pointer;
		transition: border-color 120ms, background 120ms, box-shadow 120ms;
		font-family: inherit;
		color: inherit;
		width: 100%;
	}
	.card:hover {
		background: var(--g-card);
	}
	.card.active {
		border-left: 3px solid var(--g-accent);
		background: var(--g-card);
		box-shadow: var(--g-shadow-1);
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
	}
	.glyph {
		font-size: var(--g-text-md);
		color: var(--g-ink-muted);
		width: 18px;
		text-align: center;
	}
	.label {
		font-size: var(--g-text-sm);
		font-weight: 600;
		color: var(--g-ink);
		flex: 1;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--g-good, #2f7d4f);
		flex-shrink: 0;
	}
	.dot-warn {
		background: var(--g-warn);
	}
	.metric {
		display: flex;
		align-items: baseline;
		gap: var(--g-s-1);
	}
	.big {
		font-size: var(--g-text-2xl);
		font-weight: 700;
		color: var(--g-ink);
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}
	.sub {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.status {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		flex-wrap: wrap;
	}
	.pill {
		font-size: 10px;
		padding: 2px 6px;
		border-radius: var(--g-radius-pill);
		background: color-mix(in srgb, var(--g-good, #2f7d4f) 12%, transparent);
		color: var(--g-good, #2f7d4f);
		font-weight: 600;
		letter-spacing: var(--g-track-wide);
	}
	.pill-warn {
		background: color-mix(in srgb, var(--g-warn) 15%, transparent);
		color: var(--g-warn);
	}
	.detail-count {
		font-size: 10px;
		color: var(--g-ink-muted);
	}
</style>
