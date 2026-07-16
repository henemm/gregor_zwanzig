<script lang="ts">
	// Issue #578 — CompareSmsPreview-Molecule.
	// Kanonische Quelle: molecules.jsx::CompareSmsPreview
	//
	// Token-Format ≤ 140 Zeichen. Warn-Farbe #f0a060 bei Überschreitung.
	//
	// Issue #1270 (ADR-0011): reine ANZEIGE-HÜLLE. Die Komponente baut den
	// SMS-Text nicht mehr selbst (kein Rang, keine Punktzahl — #1110) und kappt
	// auch nicht mehr selbst; beides passiert im Backend
	// (`render_compare_sms`, Budget aus CHANNEL_LIMITS) und kommt über
	// POST /api/preview/compare/{preset_id}. Vorbild:
	// preview/SmsPhoneFrame.svelte:24,59,64 (fetch → token_line/char_count zeigen).
	// Visuelle Chrome (Farben, Bubble-Optik, Zeichenzähler) bleibt unverändert.

	const COMPARE_SMS_MAX = 140;

	interface Props {
		/** Fertig gerenderter SMS-Text aus dem Backend. */
		text: string;
		/** Zeichenzahl aus dem Backend (`sms_char_count`); Fallback: text.length. */
		charCount?: number;
		class?: string;
	}

	let { text, charCount, class: className = '' }: Props = $props();

	const count = $derived(charCount ?? text.length);
	const over = $derived(count > COMPARE_SMS_MAX);
</script>

<div
	class={className}
	style:background="#0b0b0d"
	style:border-radius="var(--g-r-3)"
	style:padding="16px 14px 18px"
>
	<div style:display="flex" style:align-items="center" style:justify-content="space-between" style:margin-bottom="12px">
		<span style:color="#fff" style:font-size="12.5px" style:font-weight="600">SMS · Gregor Zwanzig</span>
		<span style:font-family="var(--g-font-mono)" style:font-size="9.5px" style:color="rgba(255,255,255,0.45)" style:letter-spacing="0.06em" style:text-transform="uppercase">flach · ohne Spalten</span>
	</div>
	<div style:max-width="280px" style:background="#3a3a3c" style:border-radius="4px 16px 16px 16px" style:padding="11px 13px">
		<div
			data-testid="compare-preview-sms-text"
			style:font-family="var(--g-font-mono)"
			style:font-size="12px"
			style:color="#fff"
			style:line-height="1.5"
			style:white-space="pre-wrap"
			style:word-break="break-word"
		>{text}</div>
	</div>
	<div style:font-family="var(--g-font-mono)" style:font-size="10px" style:color={over ? '#f0a060' : 'rgba(255,255,255,0.45)'} style:margin-top="8px">
		{count}/{COMPARE_SMS_MAX} Zeichen{over ? ' · über Budget' : ''}
	</div>
</div>
