<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Live-Mail-Vorschau (rechts, sticky).
	// 1:1 nach WM2_MailPreview/WM2_ChannelTabs/WM2_DiffBanner/WM2_EmailTable/
	// WM2_TelegramBubble/WM2_SMSLine aus screen-trip-edit-v2-weather.jsx.
	// Highlight-Prop beleuchtet die betroffene Spalte/Zelle 2,5 s auf.
	// Issue #1232 Scheibe 3b: interner Kanal-State + .ch-tabs entfallen — der
	// geteilte `LTChannelPicker` (LayoutTab) steuert den Kanal jetzt controlled
	// über die neue `channel`-Prop.
	import type { MetricEntry } from '../../trip-detail/metricsEditor.ts';
	import { CHANNEL_COL_BUDGET } from '../../trip-detail/metricsEditor.ts';
	import type { Highlight } from '../../trip-detail/metricsEditor.ts';
	import { Eyebrow } from '$lib/components/atoms';
	import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';

	interface Props {
		primaryColumns: string[];
		metricById: Record<string, MetricEntry>;
		friendlyMap: Record<string, boolean>;
		telegramKurzform: boolean;
		highlight: Highlight | null;
		channel: ChannelId;
	}

	let { primaryColumns, metricById, friendlyMap, telegramKurzform, highlight, channel }: Props = $props();

	const tgBudget = CHANNEL_COL_BUDGET.telegram;

	// Sample data 1:1 from JSX (WM2_S) — Issue #711: ind-Werte spiegeln fmt_val()-Schwellen
	const WM2_S: Record<string, { raw: string[]; ind?: string[] }> = {
		temperature:     { raw: ['6,5', '6,8', '5,5'] },
		wind_chill:      { raw: ['5,2', '4,7', '2,6'] },
		wind:            { raw: ['2',   '8',   '10'],  ind: ['ruhig','ruhig','ruhig'] },
		gust:            { raw: ['23',  '16',  '24'],  ind: ['ruhig','ruhig','ruhig'] },
		precipitation:   { raw: ['1,1', '3,3', '1,8'] },
		rain_probability:{ raw: ['100', '100', '98'],  ind: ['sehr w.','sehr w.','sehr w.'] },
		thunder:         { raw: ['–',   '–',   '–'],   ind: ['nein','nein','nein'] },
		// cloud_total: ≤90 → 🌥️ (☀️≤10/🌤️≤30/⛅≤70/🌥️≤90/☁️>90)
		cloud_total:     { raw: ['90',  '85',  '80'],  ind: ['🌥️','🌥️','🌥️'] },
		// visibility: echtes Einfach-Rendering ist Text (good/fair/poor) — kein Emoji
		visibility:      { raw: ['25',  '12',  '22'],  ind: ['gut','mäßig','gut'] },
		uv_index:        { raw: ['0,2', '0,4', '0,9'] },
		freezing_level:  { raw: ['2880','2890','2930'] },
		humidity:        { raw: ['78',  '85',  '80'] },
		dewpoint:        { raw: ['4',   '5',   '3'] },
		wind_direction:  { raw: ['N',   'N',   'NO'] },
		pressure:        { raw: ['1012','1010','1011'] },
		// sunshine: bei 0–5 Sonnenstunden + ~90% Bewölkung → bedecktes Emoji
		sunshine:        { raw: ['0',   '0',   '5'],   ind: ['☁️','☁️','🌥️'] },
		fresh_snow:      { raw: ['–',   '–',   '–'] },
		snow_depth:      { raw: ['–',   '–',   '–'] },
		snowfall_limit:  { raw: ['–',   '–',   '–'] },
		// cloud_low: ☀️≤10/🌤️≤30/⛅≤70/🌥️≤90/☁️>90 → 60→⛅, 40→⛅, 30→🌤️
		cloud_low:       { raw: ['60',  '40',  '30'],  ind: ['⛅','⛅','🌤️'] },
		// cloud_mid: 20→🌤️, 15→🌤️, 10→☀️
		cloud_mid:       { raw: ['20',  '15',  '10'],  ind: ['🌤️','🌤️','☀️'] },
		// cloud_high: 5→☀️
		cloud_high:      { raw: ['5',   '5',   '5'],   ind: ['☀️','☀️','☀️'] },
		// cape: raw [40,120,80] alle ≤300 → 🟢 (grüne Ampel)
		cape:            { raw: ['40',  '120', '80'],  ind: ['🟢','🟢','🟢'] },
		precip_type:     { raw: ['Regen','Regen','Regen'] },
	};
	const SAMPLE_HOURS = ['08', '09', '10'];

	function cell(id: string, hi: number): string {
		const s = WM2_S[id] ?? { raw: ['–', '–', '–'] };
		const useIndicator = friendlyMap[id] === true;
		if (useIndicator && s.ind) return s.ind[hi] ?? '–';
		return (s.raw)[hi] ?? '–';
	}

	function shortOf(id: string): string {
		const m = metricById[id];
		if (!m) return id.slice(0, 5);
		return m.col_label ?? (m.label.length > 6 ? m.label.slice(0, 6) : m.label);
	}

	function labelOf(id: string): string {
		return metricById[id]?.label ?? id;
	}

	function maxVal(id: string): string {
		const s = WM2_S[id] ?? { raw: ['–', '–', '–'] };
		const useIndicator = friendlyMap[id] === true;
		const vals = (useIndicator && s.ind) ? s.ind : s.raw;
		let best = vals[0];
		let bestN = parseFloat(String(best).replace(',', '.'));
		for (let i = 1; i < vals.length; i++) {
			const n = parseFloat(String(vals[i]).replace(',', '.'));
			if (!isNaN(n) && (isNaN(bestN) || n > bestN)) { best = vals[i]; bestN = n; }
		}
		const m = metricById[id];
		return m?.unit ? `${best} ${m.unit}` : String(best);
	}

	// Diff banner label
	const DIFF_LABELS: Record<string, string> = {
		moved: 'verschoben',
		added: 'neu aktiviert',
		removed: 'deaktiviert',
		mode: 'Darstellung geändert',
		preset: 'Vorschau aktualisiert',
	};

	function hlBg(kind: string): string {
		if (kind === 'removed') return 'rgba(168,50,50,0.10)';
		return 'var(--g-accent-tint)';
	}
	function hlOutline(kind: string): string {
		if (kind === 'removed') return '1.5px solid var(--g-bad)';
		return '1.5px solid var(--g-accent)';
	}

	// Telegram
	const tgInTable = $derived(primaryColumns.slice(0, tgBudget));
	const tgOverflow = $derived(primaryColumns.slice(tgBudget));
	const tgCut = $derived(primaryColumns.length > tgBudget);

	// Telegram mono table
	const COL_W = 7;
	function pad(txt: string): string {
		return String(txt).slice(0, 6).padEnd(COL_W, ' ');
	}
	const tgHeadLine = $derived('h     ' + tgInTable.map(id => pad(shortOf(id))).join(''));
	const tgDataLines = $derived(
		SAMPLE_HOURS.map((h, hi) =>
			h.padEnd(COL_W - 1, ' ') + ' ' + tgInTable.map(id => pad(cell(id, hi))).join('')
		)
	);

	// SMS line
	const SMS_TOK: Record<string, string> = {
		temperature: 'N8 D11', precipitation: 'R3.2', rain_probability: 'PR53%@12',
		wind: 'W12@11(24@13)', gust: 'G25@12(43@14)', thunder: 'TH5%@12',
	};
	const smsLine = $derived((() => {
		const tok = (id: string) => SMS_TOK[id];
		const tokens: string[] = [];
		for (const id of primaryColumns) {
			const t = tok(id);
			if (t) tokens.push(t);
		}
		return `BSPTOUR: ${[...tokens, 'Z:WATCH'].join(' ')}`;
	})());
</script>

<div class="mail-preview" data-testid="wm2-mail-preview">
	<div class="preview-eyebrow-row">
		<Eyebrow style="margin-bottom:8px">So kommt es an</Eyebrow>
		<span class="sample-badge" data-testid="wm2-sample-badge">Beispieldaten</span>
	</div>

	<div class="preview-body">
		<!-- Diff Banner -->
		{#if highlight}
			{@const bad = highlight.kind === 'removed'}
			{@const metric = highlight.id ? metricById[highlight.id] : null}
			<div class="diff-banner" class:bad data-testid="wm2-diff-banner">
				<span class="diff-dot" class:bad aria-hidden="true"></span>
				<span class="diff-text">
					{#if metric}
						<strong>{metric.label}</strong> — {DIFF_LABELS[highlight.kind] ?? highlight.kind}
					{:else}
						{DIFF_LABELS[highlight.kind] ?? 'Vorschau aktualisiert'}
					{/if}
					<span class="diff-sub">· unten hervorgehoben</span>
				</span>
			</div>
		{/if}

		<!-- Email Preview -->
		{#if channel === 'email'}
			<div class="email-frame" data-testid="wm2-email-table">
				<div class="email-chrome">
					<span class="mono chrome-l">✉ ABEND-BRIEFING</span>
					<span class="mono chrome-r">Beispiel-Tour · Etappe 1</span>
				</div>
				<div class="email-body">
					<div class="mono email-eyebrow">◷ Wetter-Briefing</div>
					<div class="email-title">Beispiel-Tour</div>
					<div class="email-sub">Beispiel-Etappe · 08–10 h</div>
					<div class="table-scroll">
						<table class="email-table mono tnum">
							<thead>
								<tr>
									<th class="time-th">Zeit</th>
									{#each primaryColumns as id}
										{@const hl = highlight && highlight.id === id}
										<th
											style:background={hl ? hlBg(highlight!.kind) : undefined}
											style:outline={hl ? hlOutline(highlight!.kind) : undefined}
											style:outline-offset={hl ? '0' : undefined}
											style:border-radius={hl ? '3px 3px 0 0' : undefined}
										>
											{shortOf(id)}
										</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each SAMPLE_HOURS as h, hi}
									<tr>
										<td class="time-td">{h}</td>
										{#each primaryColumns as id}
											{@const hl = highlight && highlight.id === id}
											<td
												style:background={hl ? hlBg(highlight!.kind) : undefined}
												style:outline={hl ? hlOutline(highlight!.kind) : undefined}
											>
												{cell(id, hi)}
											</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</div>

		<!-- Telegram Preview -->
		{:else if channel === 'telegram'}
			<div data-testid="wm2-telegram-bubble">
				<div class="tg-chat">
					<div class="tg-bubble">
						<div class="tg-meta">
							<span class="tg-avatar" aria-hidden="true">✈</span>
							<span class="tg-sender">Gregor Zwanzig</span>
							<span class="tg-tag mono">Telegram</span>
						</div>
						<div class="tg-title mono">Beispiel-Tour · Seg. 1 · 08–10 h</div>
						<div class="tg-table mono tnum">
							<div class="tg-head">{tgHeadLine}</div>
							{#each tgDataLines as line}
								<div>{line}</div>
							{/each}
						</div>
						{#if telegramKurzform && tgOverflow.length > 0}
							<div class="tg-suffix">
								<span class="mono tg-suffix-label">Tages-Max</span>
								{#each tgOverflow as id, i}
									{#if i > 0}<span class="tg-sep">·</span>{/if}
									<strong>{labelOf(id)}</strong>
									{maxVal(id)}
								{/each}
							</div>
						{/if}
					</div>
				</div>
				<div class="tg-status" class:cut={tgCut}>
					{#if tgCut}
						<strong class="tg-warn-title">{tgOverflow.length} {tgOverflow.length === 1 ? 'Metrik passt' : 'Metriken passen'} nicht in die Tabelle:</strong>
						{tgOverflow.map(id => labelOf(id)).join(', ')}.
						Telegram zeigt nur die ersten <strong>{tgBudget}</strong> — <strong>deshalb zählt die Reihenfolge.</strong>
					{:else}
						Alle <strong>{tgInTable.length}</strong> Spalten passen ins Telegram-Limit ({tgBudget}).
					{/if}
				</div>
			</div>

		<!-- SMS Preview -->
		{:else}
			<div data-testid="wm2-sms-line">
				<div class="sms-chat">
					<div class="sms-bubble mono">{smsLine}</div>
					<div class="mono sms-len">{smsLine.length}/140 Zeichen</div>
				</div>
				<div class="sms-note">
					SMS kennt keine Spalten-Reihenfolge: nur entscheidungskritische Werte werden als Kurzcodes gesendet.
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.mail-preview {
		position: sticky;
		top: 16px;
		display: flex;
		flex-direction: column;
		gap: 0;
	}
	.preview-eyebrow-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 8px;
	}
	.sample-badge {
		font-size: 10px;
		font-weight: 600;
		padding: 2px 7px;
		border-radius: 999px;
		background: rgba(192, 138, 26, 0.14);
		color: #8a6210;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}
	.preview-body {
		display: flex;
		flex-direction: column;
		gap: 0;
	}
	/* Diff Banner */
	.diff-banner {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 7px 12px;
		border-radius: var(--g-r-2);
		margin-bottom: 10px;
		background: var(--g-accent-tint);
		border-left: 2px solid var(--g-accent);
	}
	.diff-banner.bad {
		background: rgba(168, 50, 50, 0.07);
		border-left-color: var(--g-bad);
	}
	.diff-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--g-accent);
		flex-shrink: 0;
	}
	.diff-dot.bad {
		background: var(--g-bad);
	}
	.diff-text {
		font-size: 12.5px;
		color: var(--g-ink-2);
	}
	.diff-sub {
		color: var(--g-ink-4);
	}
	/* Email */
	.email-frame {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		overflow: hidden;
		background: #fff;
	}
	.email-chrome {
		padding: 8px 14px;
		background: var(--g-card-alt);
		border-bottom: 1px solid var(--g-rule-soft);
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.chrome-l {
		font-size: 9px;
		letter-spacing: 0.12em;
		color: var(--g-accent);
		font-weight: 600;
	}
	.chrome-r {
		font-size: 9px;
		color: var(--g-ink-4);
		margin-left: auto;
	}
	.email-body {
		padding: 16px 18px;
	}
	.email-eyebrow {
		font-size: 10px;
		color: var(--g-accent);
		font-weight: 600;
		margin-bottom: 2px;
	}
	.email-title {
		font-size: 22px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	.email-sub {
		font-size: 12px;
		color: var(--g-ink-2);
		margin: 2px 0 14px;
	}
	.table-scroll {
		overflow-x: auto;
	}
	.email-table {
		border-collapse: collapse;
		font-size: 12.5px;
		min-width: max-content;
		width: 100%;
	}
	.email-table th, .email-table td {
		padding: 4px 10px 4px 0;
		white-space: nowrap;
	}
	.email-table th {
		font-size: 11px;
		color: var(--g-ink-3);
		font-weight: 600;
		text-align: right;
		border-bottom: 1px solid var(--g-rule);
	}
	.email-table td {
		font-size: 12.5px;
		color: var(--g-ink);
		font-weight: 500;
		text-align: right;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.time-th {
		text-align: left !important;
	}
	.time-td {
		color: var(--g-ink-3) !important;
		font-weight: 600 !important;
		text-align: left !important;
	}
	/* Telegram */
	.tg-chat {
		background: #e9e6dc;
		border-radius: var(--g-r-3);
		padding: 14px 12px;
	}
	.tg-bubble {
		max-width: 360px;
		background: #fff;
		border-radius: 4px 14px 14px 14px;
		box-shadow: 0 1px 2px rgba(0,0,0,0.12);
		overflow: hidden;
	}
	.tg-meta {
		padding: 7px 12px 5px;
		display: flex;
		align-items: center;
		gap: 7px;
		border-bottom: 1px solid #eee;
	}
	.tg-avatar {
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: #2aabee;
		color: #fff;
		font-size: 11px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
	}
	.tg-sender {
		font-size: 12px;
		font-weight: 600;
		color: #1d1c1a;
	}
	.tg-tag {
		font-size: 9px;
		color: #9a978d;
		margin-left: auto;
	}
	.tg-title {
		padding: 10px 12px 6px;
		font-size: 11px;
		font-weight: 600;
		color: #1d1c1a;
	}
	.tg-table {
		font-size: 11px;
		line-height: 1.55;
		white-space: pre;
		overflow-x: auto;
		color: #1d1c1a;
		background: #f6f4ee;
		border-radius: 4px;
		padding: 6px 8px;
		margin: 0 12px 10px;
	}
	.tg-head {
		color: #6b675c;
	}
	.tg-suffix {
		padding: 0 12px 12px;
		font-size: 11.5px;
		color: #3a3835;
		line-height: 1.6;
	}
	.tg-suffix-label {
		font-size: 10px;
		color: #6b675c;
		margin-right: 4px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.tg-sep {
		color: #b9b4a6;
		margin: 0 3px;
	}
	.tg-status {
		margin-top: 9px;
		padding: 9px 12px;
		border-radius: var(--g-r-2);
		border-left: 2px solid var(--g-good);
		background: rgba(61, 107, 58, 0.06);
		font-size: 12px;
		color: var(--g-ink-2);
		line-height: 1.5;
	}
	.tg-status.cut {
		border-left-color: var(--g-warn);
		background: rgba(192, 138, 26, 0.07);
	}
	.tg-warn-title {
		color: #8a6210;
	}
	/* SMS */
	.sms-chat {
		background: #e9e6dc;
		border-radius: var(--g-r-3);
		padding: 14px 12px;
	}
	.sms-bubble {
		max-width: 300px;
		background: #e5e5ea;
		color: #1d1c1a;
		border-radius: 4px 14px 14px 14px;
		padding: 10px 13px;
		font-size: 12.5px;
		line-height: 1.55;
		word-break: break-all;
	}
	.sms-len {
		font-size: 10px;
		color: #6b675c;
		margin-top: 5px;
	}
	.sms-note {
		margin-top: 9px;
		padding: 9px 12px;
		border-radius: var(--g-r-2);
		border-left: 2px solid var(--g-warn);
		background: rgba(192, 138, 26, 0.06);
		font-size: 12px;
		color: var(--g-ink-2);
		line-height: 1.5;
	}
</style>
