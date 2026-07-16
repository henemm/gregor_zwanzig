<script lang="ts">
	// Issue #578 — CompareChatBubble-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareChatBubble
	//
	// Eingehende Bubble in echter Messenger-Optik.
	// Telegram: backdrop=#17212b, bubble=#1e2c3a, accent=#5ea9dd
	//
	// Issue #1270 (ADR-0011): reine ANZEIGE-HÜLLE. Die Komponente rendert den
	// Telegram-Inhalt nicht mehr selbst — kein Spalten-Budget, kein Rang, keine
	// Punktzahl, keine Gewinner-Hervorhebung (Score/Rang sind abgeschafft, #1110;
	// sie dürfen nicht über die Vorschau ins UI zurückkehren). Der fertige Text
	// kommt aus dem Backend (`render_compare_telegram`) über
	// POST /api/preview/compare/{preset_id}. Vorbild: preview/SmsPhoneFrame.svelte:24,59,64.
	// Visuelle Chrome (Farben, Bubble-Optik, Kopfzeile, Fußzeile) bleibt unverändert.

	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';

	interface Props {
		/** Fertig gerenderter Telegram-Text aus dem Backend. */
		text: string;
		channel?: 'telegram';
		class?: string;
	}

	let { text, channel: _channel = 'telegram', class: className = '' }: Props = $props();

	// Farben Telegram
	const backdrop = '#17212b';
	const bubbleBg = '#1e2c3a';
	const accent = '#5ea9dd';
	// Kanal-Budget-Label (Chrome). Einzige Budget-Quelle bleibt
	// CHANNEL_COL_BUDGET (metricsEditor.ts) — hier nur als Beschriftung, die
	// Kappung selbst passiert im Backend (CHANNEL_LIMITS).
	const maxLabel = `Telegram · max ${CHANNEL_COL_BUDGET.telegram} Spalten`;
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
		<div
			data-testid="compare-preview-telegram-text"
			style:font-family="var(--g-font-mono)"
			style:font-size="12px"
			style:color="#fff"
			style:line-height="1.5"
			style:white-space="pre-wrap"
			style:word-break="break-word"
		>{text}</div>

		<div style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:color="rgba(255,255,255,0.4)" style:margin-top="11px" style:text-align="right">
			via gregor.zwanzig
		</div>
	</div>
</div>
