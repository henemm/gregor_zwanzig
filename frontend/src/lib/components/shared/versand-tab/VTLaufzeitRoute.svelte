<script lang="ts">
	// VT_LaufzeitRoute — Issue #1232 Scheibe 1: "Laufzeit" (route = read-only aus
	// Etappen) im geteilten VersandTab-Organism.
	//
	// 1:1-Struktur aus versand-tab.jsx (VT_LaufzeitRoute). KEIN editierbares
	// Datumsfeld (AC-5) — das Enddatum kommt aus den Etappen, der Button
	// wechselt in den Etappen-Tab.
	//
	// Spec: docs/specs/modules/versand_tab_route.md (AC-5)

	import { Eyebrow, Btn } from '$lib/components/atoms';

	interface Props {
		tripEnd: string | null;
		onOpenStages: () => void;
	}
	let { tripEnd, onOpenStages }: Props = $props();
</script>

<div>
	<Eyebrow style="margin-bottom: 10px;">Laufzeit</Eyebrow>
	<div class="vt-laufzeit-box" data-testid="briefings-laufzeit">
		<span class="vt-laufzeit-dot"></span>
		<div class="vt-laufzeit-text">
			<div class="vt-laufzeit-title">Läuft mit der Tour · endet {tripEnd ?? '—'}</div>
			<div class="vt-laufzeit-sub">
				Das Enddatum ergibt sich aus den Etappen — es wird dort gepflegt, nicht hier.
			</div>
		</div>
		<Btn variant="ghost" size="sm" onclick={onOpenStages}>Etappen öffnen →</Btn>
	</div>
</div>

<style>
	.vt-laufzeit-box {
		padding: 16px 20px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 12px);
		display: flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
	}
	.vt-laufzeit-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--g-good, #2f6f4f);
		flex-shrink: 0;
	}
	.vt-laufzeit-text {
		flex: 1;
		min-width: 180px;
	}
	.vt-laufzeit-title {
		font-size: 14.5px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.vt-laufzeit-sub {
		font-size: 12.5px;
		color: var(--g-ink-3);
		margin-top: 3px;
		line-height: 1.5;
	}

	@media (max-width: 899px) {
		.vt-laufzeit-box {
			padding: 14px;
		}
	}
</style>
