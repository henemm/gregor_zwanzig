<script lang="ts">
	// Issue #578 — CompareChatBubble-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareChatBubble
	//
	// Eingehende Bubble in echter Messenger-Optik. Spalten nach Kanal gekappt.
	// Signal: backdrop=#0b0b0d, bubble=#26252b, accent=#2c6bed
	// Telegram: backdrop=#17212b, bubble=#1e2c3a, accent=#5ea9dd

	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';

	interface Col {
		key: string;
		label: string;
		primary?: boolean;
	}

	interface Row {
		id: string;
		rank: number;
		score: string | number;
		[key: string]: unknown;
	}

	interface Profile {
		code: string;
		question: string;
		cols: Col[];
	}

	interface Data {
		rows: Row[];
		locations: Record<string, { name: string }>;
	}

	interface Props {
		channel?: 'telegram';
		profile: Profile;
		data: Data;
		subscriptionName?: string;
		class?: string;
	}

	let { channel = 'telegram', profile, data, subscriptionName, class: className = '' }: Props = $props();

	// Kanal-Constraints: Telegram-Budget minus 2 (Rang+Ort). Signal entfernt (#610).
	// Issue #1232 Scheibe 3a: einzige Kappungs-Quelle CHANNEL_COL_BUDGET (metricsEditor.ts).
	const MAXCOLS: Record<string, number> = { telegram: CHANNEL_COL_BUDGET.telegram };

	function compareShownCols(prof: Profile, ch: string): Col[] {
		const max = MAXCOLS[ch] ?? CHANNEL_COL_BUDGET.telegram;
		const metrics = prof.cols.filter((c) => c.key !== 'score');
		const ordered = [...metrics.filter((c) => c.primary), ...metrics.filter((c) => !c.primary)];
		return ordered.slice(0, Math.max(1, max - 2));
	}

	const shown = $derived(compareShownCols(profile, channel));

	// Farben Telegram
	const backdrop = '#17212b';
	const bubbleBg = '#1e2c3a';
	const accent = '#5ea9dd';
	const maxLabel = `Telegram · max ${CHANNEL_COL_BUDGET.telegram} Spalten`;

	function fmt(col: Col, row: Row): string {
		return String(row[col.key] ?? '—');
	}
</script>

<div
	class={className}
	style:background={backdrop}
	style:border-radius="var(--g-r-3)"
	style:padding="16px 14px 18px"
	style:overflow="hidden"
>
	<div style:display="flex" style:align-items="center" style:justify-content="space-between" style:margin-bottom="12px">
		<span style:display="inline-flex" style:align-items="center" style:gap="7px" style:color="#fff" style:font-size="12.5px" style:font-weight="600">
			<span style:width="8px" style:height="8px" style:border-radius="50%" style:background={accent}></span>
			Gregor Zwanzig
		</span>
		<span style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:color="rgba(255,255,255,0.45)" style:letter-spacing="0.06em" style:text-transform="uppercase">{maxLabel}</span>
	</div>

	<div
		style:max-width="300px"
		style:background={bubbleBg}
		style:border-radius="4px 16px 16px 16px"
		style:padding="12px 13px 10px"
		style:box-shadow="0 1px 1px rgba(0,0,0,0.3)"
	>
		<div style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:letter-spacing="0.12em" style:color={accent} style:font-weight="700" style:margin-bottom="3px">
			ORTS-VERGLEICH · {profile.code}
		</div>
		<div style:font-size="13px" style:font-weight="600" style:color="#fff" style:line-height="1.3" style:margin-bottom="10px">
			{profile.question}
		</div>

		<div style:display="flex" style:flex-direction="column" style:gap="9px">
			{#each data.rows as r (r.id)}
				{@const loc = data.locations[r.id]}
				{@const win = r.rank === 1}
				<div style:border-top={r.rank === 1 ? 'none' : '1px solid rgba(255,255,255,0.08)'} style:padding-top={r.rank === 1 ? '0' : '8px'}>
					<div style:display="flex" style:align-items="baseline" style:gap="7px">
						<span style:font-family="var(--g-font-mono)" style:font-size="11px" style:font-weight="700" style:color={win ? '#7bd88f' : 'rgba(255,255,255,0.6)'}>#{r.rank}</span>
						<span style:font-size="12.5px" style:font-weight="600" style:color="#fff" style:flex="1" style:min-width="0" style:white-space="nowrap" style:overflow="hidden" style:text-overflow="ellipsis">{loc?.name ?? r.id}</span>
						<span style:font-family="var(--g-font-mono)" style:font-size="12.5px" style:font-weight="700" style:color={win ? '#7bd88f' : '#fff'}>{r.score}</span>
					</div>
					<div style:font-family="var(--g-font-mono)" style:font-size="10.5px" style:color="rgba(255,255,255,0.62)" style:line-height="1.45" style:margin-top="2px" style:display="flex" style:flex-wrap="wrap" style:gap="0 8px">
						{#each shown as col (col.key)}
							<span>{col.label} {fmt(col, r)}</span>
						{/each}
					</div>
				</div>
			{/each}
		</div>

		<div style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:color="rgba(255,255,255,0.4)" style:margin-top="11px" style:text-align="right">
			via gregor.zwanzig · 06:00
		</div>
	</div>
</div>
