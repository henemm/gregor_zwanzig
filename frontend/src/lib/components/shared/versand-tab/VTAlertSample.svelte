<script lang="ts">
	// VT_AlertSample — Issue #1232 Scheibe 2b: "Beispiel-Warnung" im geteilten
	// VersandTab-Organism, statisch, kontext-abhängiges Subjekt (Ort statt
	// Etappe). 1:1 aus versand-tab.jsx VT_ALERT_SAMPLE.vergleich — KEIN
	// AlertPreviewCard-Neubau (KL-4: kein Live-Preview-Datenmodell für
	// Vergleiche vorhanden).
	//
	// Spec: docs/specs/modules/versand_tab_vergleich.md (Implementation Details Punkt 2.4)
	import { Eyebrow } from '$lib/components/atoms';

	interface Props {
		context?: 'route' | 'vergleich';
	}
	let { context = 'route' }: Props = $props();

	interface SampleRow {
		metric: string;
		from: string;
		to: string;
		subject: string;
	}

	const SAMPLES: Record<'route' | 'vergleich', SampleRow[]> = {
		route: [
			{ metric: 'Gewitter', from: '15 %', to: '60 %', subject: 'Etappe 3 · 14–18 Uhr' },
			{ metric: 'Böen', from: '45 km/h', to: '72 km/h', subject: 'Etappe 3 · 14–16 Uhr' },
			{ metric: 'Sichtweite', from: '15 km', to: '6 km', subject: 'Etappe 3 · 14–18 Uhr' }
		],
		vergleich: [
			{ metric: 'Wind (Mittel)', from: '22 km/h', to: '48 km/h', subject: 'Aberg · Fr 14–18 Uhr' },
			{ metric: 'Neuschnee', from: '5 cm', to: '18 cm', subject: 'Dientalm · Fr–Sa' },
			{ metric: 'Sichtweite', from: '12 km', to: '4 km', subject: 'Karbachalm · Sa 09–12' }
		]
	};
	const HEADLINE: Record<'route' | 'vergleich', string> = {
		route: 'KHW 403',
		vergleich: 'Skitouren Hochkönig'
	};
	const SUBJECT_LABEL: Record<'route' | 'vergleich', string> = {
		route: 'Etappe · Zeitraum',
		vergleich: 'Ort · Zeitraum'
	};

	const rows = $derived(SAMPLES[context] ?? SAMPLES.route);
	const headline = $derived(HEADLINE[context] ?? HEADLINE.route);
	const subjectLabel = $derived(SUBJECT_LABEL[context] ?? SUBJECT_LABEL.route);
</script>

<div>
	<Eyebrow style="margin-bottom: 4px;">Beispiel-Warnung</Eyebrow>
	<p class="vt-sample-lead">
		So sieht eine ausgelöste Warn-Mail aus, wenn ein Wert den Wertebereich verlässt.
	</p>
	<div class="vt-sample-card" data-testid="versand-alert-sample">
		<div class="vt-sample-head">
			<div>
				<div class="mono vt-sample-eyebrow">ALERT · {headline}</div>
				<div class="vt-sample-title">Wetter-Änderung erkannt</div>
			</div>
			<div class="mono vt-sample-time">Mi 14.05.<br />14:23</div>
		</div>

		<table class="vt-sample-table">
			<thead>
				<tr>
					<th class="vt-th-left">Metrik</th>
					<th class="vt-th-right">Vorher</th>
					<th class="vt-th-right">Nachher</th>
					<th class="vt-th-left">{subjectLabel}</th>
				</tr>
			</thead>
			<tbody>
				{#each rows as r (r.metric)}
					<tr>
						<td class="vt-td-metric">{r.metric}</td>
						<td class="mono vt-td-from">{r.from}</td>
						<td class="mono vt-td-to">{r.to}</td>
						<td class="mono vt-td-subject">{r.subject}</td>
					</tr>
				{/each}
			</tbody>
		</table>

		<div class="vt-sample-mobile">
			{#each rows as r, i (r.metric)}
				<div class="vt-sample-mobile-row" class:first={i === 0}>
					<div class="vt-sample-mobile-top">
						<span class="vt-td-metric">{r.metric}</span>
						<span class="mono vt-sample-mobile-values">
							<span class="vt-td-from">{r.from}</span>
							<span class="vt-arrow">→</span>
							<span class="vt-td-to">{r.to}</span>
						</span>
					</div>
					<div class="mono vt-sample-mobile-subject">{r.subject}</div>
				</div>
			{/each}
		</div>
	</div>
</div>

<style>
	.vt-sample-lead {
		font-size: 13px;
		color: var(--g-ink-3);
		margin: 0 0 14px;
		line-height: 1.5;
		max-width: 560px;
	}
	.vt-sample-card {
		background: #fff;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2, 8px);
		max-width: 560px;
		overflow: hidden;
		font-family: Helvetica, Arial, sans-serif;
	}
	.vt-sample-head {
		background: var(--g-accent);
		color: #fff;
		padding: 12px 18px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.vt-sample-eyebrow {
		font-size: 10px;
		letter-spacing: 0.1em;
		opacity: 0.9;
	}
	.vt-sample-title {
		font-size: 16px;
		font-weight: 600;
		margin-top: 2px;
	}
	.vt-sample-time {
		font-size: 10px;
		opacity: 0.9;
		text-align: right;
		line-height: 1.5;
	}
	.vt-sample-table {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
	}
	.vt-sample-table thead tr {
		background: rgba(196, 90, 42, 0.05);
	}
	.vt-th-left,
	.vt-th-right {
		padding: 8px 18px;
		font-size: 10.5px;
		color: var(--g-ink-3);
		font-weight: 600;
	}
	.vt-th-right {
		padding: 8px 8px;
		text-align: right;
	}
	.vt-sample-table tbody tr {
		border-top: 1px solid var(--g-rule-soft);
	}
	.vt-td-metric {
		padding: 9px 18px;
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.vt-td-from {
		padding: 9px 8px;
		font-size: 12px;
		text-align: right;
		color: var(--g-ink-3);
	}
	.vt-td-to {
		padding: 9px 8px;
		font-size: 12px;
		text-align: right;
		color: var(--g-accent-deep);
		font-weight: 600;
	}
	.vt-td-subject {
		padding: 9px 18px;
		font-size: 11px;
		color: var(--g-ink-3);
	}
	.vt-sample-mobile {
		display: none;
	}

	@media (max-width: 899px) {
		.vt-sample-table {
			display: none;
		}
		.vt-sample-mobile {
			display: block;
		}
		.vt-sample-mobile-row {
			padding: 10px 14px;
			border-top: 1px solid var(--g-rule-soft);
		}
		.vt-sample-mobile-row.first {
			border-top: none;
		}
		.vt-sample-mobile-top {
			display: flex;
			align-items: baseline;
			justify-content: space-between;
			gap: 8px;
		}
		.vt-sample-mobile-top .vt-td-metric {
			padding: 0;
			font-size: 14px;
		}
		.vt-sample-mobile-values {
			font-size: 12.5px;
		}
		.vt-sample-mobile-values .vt-td-from {
			padding: 0;
		}
		.vt-sample-mobile-values .vt-td-to {
			padding: 0;
		}
		.vt-arrow {
			color: var(--g-ink-4);
			margin: 0 5px;
		}
		.vt-sample-mobile-subject {
			font-size: 10.5px;
			color: var(--g-ink-3);
			margin-top: 2px;
		}
	}
</style>
