/* Mobile · Ortsvergleich · Detail
 * ─────────────────────────────────────────────────────────────────────
 * Mobile-Pendant zur Desktop-Detail-Seite (Charter §3 v1.1, Pattern Detail-Seite).
 * Zeigt Setup + Monitoring-Status + Aktionen — NICHT das Tages-Briefing
 * (CLAUDE.md: App = Einrichtung/Monitoring, kein Reader).
 *
 * Atomic Design: nutzt CompareStatusPill, CompareLocationRow (dense),
 * CompareIdealRow (dense), CompareLayoutRow (dense), compareActions +
 * DetailRow aus molecules.jsx. Lokale Reste mit CDM_-Prefix (Babel-Scope).
 */

const CDM_CHANNEL_LABEL = { email: "Email", signal: "Signal", telegram: "Telegram", sms: "SMS" };

function ScreenCompareDetailMobile({ subId = "skitour-hochkoenig" }) {
  const subs = window.MOCK_COMPARE_SUBS || [];
  const sub = subs.find(s => s.id === subId) || subs[0];
  const [actions, setActions] = React.useState(false);
  if (!sub) return null;

  const active = sub.status === "active";
  const locs = sub.locationIds
    .map(id => (window.MOCK_LOCATIONS || []).find(l => l.id === id))
    .filter(Boolean);

  const right = (
    <div style={{ display: "flex" }}>
      <IconBtn kind="edit" label="Bearbeiten"/>
      <IconBtn kind="more" label="Aktionen" onClick={() => setActions(true)}/>
    </div>
  );

  return (
    <MobileShell
      active="compare" leftIcon="back" title={sub.name} eyebrow="Orts-Vergleich · Detail"
      right={right} phoneHeight={812}
      sheet={actions && <CDM_ActionSheet status={sub.status} onClose={() => setActions(false)}/>}>
      <ScreenScroll padding={0}>
        <div style={{ padding: "12px 16px 28px" }}>

          {/* Status + Kontext */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <CompareStatusPill status={sub.status}/>
            <span style={{ fontSize: 12.5, color: "var(--g-ink-3)" }}>{sub.profileLabel} · {locs.length} Orte</span>
          </div>
          <div style={{ fontSize: 14, color: "var(--g-ink-2)", marginBottom: 14 }}>{sub.region}</div>

          {/* Monitoring 2x2 */}
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", padding: 14, marginBottom: 18,
          }}>
            <CDM_Stat label="Status">{active ? "Läuft autom." : "Pausiert"}</CDM_Stat>
            <CDM_Stat label="Nächster Versand">{sub.nextSend}</CDM_Stat>
            <CDM_Stat label="Zuletzt raus">{sub.lastSent}</CDM_Stat>
            <CDM_Stat label="Kanäle">{sub.channels.map(c => CDM_CHANNEL_LABEL[c]).join(" · ") || "—"}</CDM_Stat>
          </div>

          {/* Verglichene Orte */}
          <CDM_SectionH title="Verglichene Orte" hint={`${locs.length} Kandidaten · Ranking`}/>
          <div style={{
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", overflow: "hidden", marginBottom: 18,
          }}>
            {locs.length === 0
              ? <div style={{ padding: 16, fontSize: 13, color: "var(--g-ink-4)" }}>Noch keine Orte gewählt.</div>
              : locs.map((l, i) => <CompareLocationRow key={l.id} loc={l} index={i} dense/>)}
          </div>

          {/* Idealwerte */}
          <CDM_SectionH title="Idealwerte" hint="bestimmt das Ranking"/>
          <div style={{
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", padding: "4px 14px", marginBottom: 18,
          }}>
            {sub.ideals.map((it, i) => (
              <CompareIdealRow key={i} item={it} dense last={i === sub.ideals.length - 1}/>
            ))}
          </div>

          {/* Layout pro Kanal */}
          <CDM_SectionH title="Layout pro Kanal" hint="was im Briefing steht"/>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 18 }}>
            {sub.channels.length === 0
              ? <div style={{ fontSize: 13, color: "var(--g-ink-4)" }}>Noch keine Kanäle konfiguriert.</div>
              : sub.channels.map(ch => (
                  <CompareLayoutRow key={ch} channel={ch} cols={sub.layout[ch] || []} dense/>
                ))}
          </div>

          {/* Versand (DetailRow-Molecule) */}
          <CDM_SectionH title="Versand"/>
          <div style={{
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", padding: "4px 14px 12px", marginBottom: 18,
          }}>
            <DetailRow label="Rhythmus" value={sub.schedule}/>
            <DetailRow label="Vorausschau" value={sub.horizon}/>
            <DetailRow label="Nächster" value={sub.nextSend} divider="none"/>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
              {sub.channels.length === 0
                ? <span style={{ fontSize: 12, color: "var(--g-ink-4)" }}>Keine Kanäle</span>
                : sub.channels.map(c => <Pill key={c} tone="neutral">{CDM_CHANNEL_LABEL[c]}</Pill>)}
            </div>
          </div>

          {/* Vorschau · Prüfung */}
          <div style={{
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-3)",
            padding: 14, marginBottom: 16,
          }}>
            <Eyebrow style={{ marginBottom: 10 }}>Vorschau · Prüfung</Eyebrow>
            <CDM_MailThumb/>
            <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5, margin: "12px 0 12px" }}>
              So sieht dein Briefing in der Mail aus — zum <strong>Prüfen</strong> der Konfiguration.
              Gelesen wird es unterwegs im Postfach, nicht hier.
            </div>
            <MBtn variant="ghost" block size="lg">Vorschau öffnen</MBtn>
          </div>

          <MBtn variant="quiet" block size="lg">Test-Briefing jetzt senden</MBtn>
        </div>
      </ScreenScroll>
    </MobileShell>
  );
}

function CDM_Stat({ label, children }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--g-ink)", lineHeight: 1.25 }}>{children}</div>
    </div>
  );
}

function CDM_SectionH({ title, hint }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
      <Eyebrow>{title}</Eyebrow>
      {hint && <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>{hint}</span>}
    </div>
  );
}

function CDM_MailThumb() {
  const Bar = ({ w, c = "var(--g-rule)" }) => (<div style={{ height: 6, borderRadius: 3, background: c, width: w }}/>);
  return (
    <div style={{ border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", background: "var(--g-paper)", padding: 12, display: "flex", flexDirection: "column", gap: 7 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 1 }}>
        <Dot tone="good" size={7}/><Bar w={110} c="var(--g-ink-3)"/>
      </div>
      <Bar w="78%"/>
      <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "1px 0" }}/>
      <Bar w="100%" c="var(--g-accent-tint)"/>
      <Bar w="90%" c="var(--g-accent-tint)"/>
      <Bar w="58%"/>
    </div>
  );
}

/* Sekundäraktionen als Bottom-Sheet (Charter §6 · compareActions). */
function CDM_ActionSheet({ status, onClose }) {
  const items = compareActions(status).filter(a => a.key !== "edit"); /* Bearbeiten = TopBar-Icon */
  return (
    <Sheet open onClose={onClose} title="Aktionen" snap="peek">
      <div style={{ display: "flex", flexDirection: "column" }}>
        {items.map(it => (
          <button key={it.key} onClick={onClose} style={{
            display: "flex", alignItems: "center", gap: 14, minHeight: 52,
            padding: "12px 4px", background: "transparent", border: "none",
            borderBottom: "1px solid var(--g-rule-soft)", cursor: "pointer", textAlign: "left",
            fontSize: 15, fontWeight: 500,
            color: it.danger ? "var(--g-bad)" : "var(--g-ink)",
          }}>
            <MIcon kind={it.icon} size={20} color={it.danger ? "var(--g-bad)" : "var(--g-ink-2)"}/>
            {it.label}
          </button>
        ))}
      </div>
    </Sheet>
  );
}

window.ScreenCompareDetailMobile = ScreenCompareDetailMobile;
