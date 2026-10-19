<script lang="ts">
	// Issue #189 — SMS-Vorschau im iOS-Phone-Frame.
	// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
	// Issue #2283: inhaltsgetrieben — Text und Zeichenzahl kommen aus dem
	// geteilten Lader (shared/previewLoader.ts), der Baustein ruft nichts ab.
	// `limit` ist das Zeichenbudget des Kanals (Trip 160, Vergleich 153, #1719 S3).
	import { charCountStatus } from './previewHelpers';

	// `tripToken`: Legende und Stub-Pille beschreiben das Trip-SMS-Token — im
	// Ortsvergleich (anderes SMS-Format) entfallen beide. Faehigkeit statt
	// `context`, damit ausserhalb von shared/ keine Herkunfts-Verzweigung entsteht
	// (context_herkunft_baseline_ausserhalb_shared); PreviewTab setzt sie wie `limit`.
	interface Props { text: string; charCount?: number; limit?: number; tripToken?: boolean; }
	let { text, charCount, limit = 160, tripToken = true }: Props = $props();

	const count = $derived(charCount ?? text.length);
	let status = $derived(charCountStatus(count, limit));

	// Stub-Heuristik: echtes Spec-Token enthält ":" (z.B. "KHW_00B: N3 D11 …").
	// Email-Subject hat Leerzeichen + Wortzeichen, aber kein ":" oder "@".
	let isStub = $derived(
		tripToken && !!text && !text.includes(':') && !text.includes('@') && /\s/.test(text) && /[a-zäöüß]/i.test(text)
	);
</script>

<div class="sms-shell" data-testid="sms-phone-wrapper">
	{#if isStub}
		<span class="stub-pill" data-testid="sms-stub-pill">SMS-Token-Pipeline folgt (#188)</span>
	{/if}
	<div class="phone-frame">
		<div class="phone-screen">
			<div class="bubble" data-testid="sms-token-bubble">{text}</div>
		</div>
	</div>
	<p class="char-count char-count-{status}" data-testid="sms-char-count">{count}/{limit}</p>
	{#if tripToken}
		<p class="legend">
			Spec-Format SMS — Reihenfolge: Subject · Nacht · Tag · Regen · Druck · Wind · Gust · Gewitter · Stirnlampe · Risiko
		</p>
	{/if}
</div>

<style>
	.sms-shell { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
	.stub-pill {
		display: inline-block; padding: 0.25rem 0.625rem; font-size: 0.75rem; font-weight: 500;
		color: var(--g-ink); background: var(--g-warning); border-radius: 99rem;
	}
	.phone-frame {
		position: relative; width: 320px; background: var(--g-ink); border-radius: 36px;
		padding: 36px 14px 28px;
		box-shadow: var(--g-shadow-1, var(--g-elev-1, 0 1px 3px rgba(26, 26, 24, 0.08)));
	}
	.phone-frame::before {
		content: ''; position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
		width: 60px; height: 18px; background: black; border-radius: 12px;
	}
	.phone-screen {
		background: var(--g-paper); border-radius: 18px; min-height: 200px; padding: 14px;
		display: flex; flex-direction: column; justify-content: center;
	}
	.bubble {
		background: var(--g-paper); color: var(--g-ink);
		font-family: var(--g-font-data, 'JetBrains Mono', ui-monospace, monospace);
		font-size: 13px; line-height: 1.45; word-break: break-word;
		padding: 8px 10px; border: 1px solid var(--g-ink-faint); border-radius: 14px;
	}
	.char-count {
		font-family: var(--g-font-data, 'JetBrains Mono', monospace);
		font-size: 0.8125rem; margin: 0;
	}
	.char-count-ok { color: var(--g-ink); }
	.char-count-warn { color: var(--g-warning); }
	.char-count-over { color: var(--g-danger); }
	.legend {
		max-width: 320px; font-size: 0.6875rem; line-height: 1.4;
		color: var(--g-ink-muted); text-align: center; margin: 0;
	}
</style>
