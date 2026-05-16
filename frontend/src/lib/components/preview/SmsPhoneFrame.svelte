<script lang="ts">
	// Issue #189 — SMS-Vorschau im iOS-Phone-Frame.
	// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
	import { buildPreviewUrl, charCountStatus, type ReportType } from './previewHelpers';

	interface Props {
		tripId: string;
		type: ReportType;
		date?: string;
	}
	let { tripId, type, date }: Props = $props();

	interface SmsPayload { subject: string; token_line: string; char_count: number; }

	let payload = $state<SmsPayload | null>(null);
	let loading = $state<boolean>(true);
	let error = $state<string | null>(null);

	$effect(() => {
		const controller = new AbortController();
		const url = buildPreviewUrl('sms', tripId, type, date);
		loading = true; error = null; payload = null;
		fetch(url, { credentials: 'same-origin', signal: controller.signal }).then(async (res) => {
			if (!res.ok) {
				const detail = await res.text();
				error = `Vorschau konnte nicht geladen werden (HTTP ${res.status}). ${detail}`;
				loading = false; return;
			}
			payload = (await res.json()) as SmsPayload;
			loading = false;
		}).catch((err: unknown) => {
			if (err instanceof Error && err.name === 'AbortError') return;
			const msg = err instanceof Error ? err.message : String(err);
			error = `Netzwerkfehler: ${msg}`;
			loading = false;
		});
		return () => controller.abort();
	});

	// Stub-Heuristik: echtes Spec-Token enthält ":" (z.B. "KHW_00B: N3 D11 …").
	// Email-Subject hat Leerzeichen + Wortzeichen, aber kein ":" oder "@".
	let isStub = $derived.by(() => {
		const t = payload?.token_line ?? '';
		return !!t && !t.includes(':') && !t.includes('@') && /\s/.test(t) && /[a-zäöüß]/i.test(t);
	});
	let status = $derived(payload ? charCountStatus(payload.char_count) : 'ok');
</script>

<div class="sms-shell" data-testid="sms-phone-wrapper">
	{#if isStub}
		<span class="stub-pill" data-testid="sms-stub-pill">SMS-Token-Pipeline folgt (#188)</span>
	{/if}
	<div class="phone-frame">
		<div class="phone-screen">
			{#if loading}
				<p class="state-msg">Vorschau wird geladen…</p>
			{:else if error}
				<p class="state-msg error" data-testid="sms-error">{error}</p>
			{:else if payload}
				<div class="bubble" data-testid="sms-token-bubble">{payload.token_line}</div>
			{/if}
		</div>
	</div>
	{#if payload && !error}
		<p class="char-count char-count-{status}" data-testid="sms-char-count">{payload.char_count}/160</p>
	{/if}
	<p class="legend">
		Spec-Format SMS — Reihenfolge: Subject · Nacht · Tag · Regen · Druck · Wind · Gust · Gewitter · Stirnlampe · Risiko
	</p>
</div>

<style>
	.sms-shell { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
	.stub-pill {
		display: inline-block; padding: 0.25rem 0.625rem; font-size: 0.75rem; font-weight: 500;
		color: var(--g-ink, #1a1a18); background: var(--g-warning, #c8882a); border-radius: 99rem;
	}
	.phone-frame {
		position: relative; width: 320px; background: #1a1a18; border-radius: 36px;
		padding: 36px 14px 28px;
		box-shadow: var(--g-shadow-1, var(--g-elev-1, 0 1px 3px rgba(26, 26, 24, 0.08)));
	}
	.phone-frame::before {
		content: ''; position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
		width: 60px; height: 18px; background: #000; border-radius: 12px;
	}
	.phone-screen {
		background: var(--g-paper, #f6f4ee); border-radius: 18px; min-height: 200px; padding: 14px;
		display: flex; flex-direction: column; justify-content: center;
	}
	.bubble {
		background: var(--g-paper, #f6f4ee); color: var(--g-ink, #1a1a18);
		font-family: var(--g-font-data, 'JetBrains Mono', ui-monospace, monospace);
		font-size: 13px; line-height: 1.45; word-break: break-word;
		padding: 8px 10px; border: 1px solid var(--g-ink-faint, #9c9a90); border-radius: 14px;
	}
	.state-msg { font-size: 0.8125rem; color: var(--g-ink, #1a1a18); text-align: center; }
	.state-msg.error { color: #b03a2e; }
	.char-count {
		font-family: var(--g-font-data, 'JetBrains Mono', monospace);
		font-size: 0.8125rem; margin: 0;
	}
	.char-count-ok { color: var(--g-ink, #1a1a18); }
	.char-count-warn { color: var(--g-warning, #b67700); }
	.char-count-over { color: #b03a2e; }
	.legend {
		max-width: 320px; font-size: 0.6875rem; line-height: 1.4;
		color: var(--g-ink-muted, #5c5a52); text-align: center; margin: 0;
	}
</style>
