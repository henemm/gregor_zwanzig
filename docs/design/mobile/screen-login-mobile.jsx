/* Mobile · Login
 * Pattern: Vollbild ohne Shell. Logo + Form. Magic-Link bevorzugt, Passwort als Sekundär.
 */

function ScreenLoginMobile() {
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopoBg opacity={0.18}/>

        <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column", padding: "24px 20px 0", justifyContent: "space-between" }}>

          {/* Top: Logo */}
          <div style={{ marginTop: 24 }}>
            <Logo size={28}/>
          </div>

          {/* Mid: Form */}
          <div style={{ marginBottom: 40 }}>
            <h1 style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.1, margin: "0 0 8px" }}>
              Willkommen zurück.
            </h1>
            <div style={{ fontSize: 14, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 28 }}>
              Wetter-Briefings für deine Touren — wann, wo und in welcher Tiefe DU sie willst.
            </div>

            <MField label="Email">
              <MInput type="email" placeholder="dein@email.com" defaultValue="gregor_zwanzig@henemm.com"/>
            </MField>

            <MBtn variant="primary" size="lg" block style={{ marginTop: 8, marginBottom: 14 }}>
              Magic-Link anfordern →
            </MBtn>

            <div style={{
              display: "flex", alignItems: "center", gap: 10, color: "var(--g-ink-4)",
              fontSize: 11, fontFamily: "var(--g-font-mono)", textTransform: "uppercase",
              letterSpacing: "0.1em", margin: "12px 0 14px",
            }}>
              <div style={{ flex: 1, height: 1, background: "var(--g-rule)" }}/>
              <span>oder</span>
              <div style={{ flex: 1, height: 1, background: "var(--g-rule)" }}/>
            </div>

            <MBtn variant="ghost" size="lg" block style={{ marginBottom: 8 }}>Mit Passkey anmelden</MBtn>
            <MBtn variant="quiet" size="md" block>Mit Passwort anmelden</MBtn>
          </div>

          {/* Bottom: Footer */}
          <div style={{
            paddingBottom: "calc(20px + env(safe-area-inset-bottom))",
            fontSize: 12, color: "var(--g-ink-4)", textAlign: "center", lineHeight: 1.5,
          }}>
            Neu hier?{" "}
            <a href="#" style={{ color: "var(--g-accent)", textDecoration: "none", fontWeight: 600 }}>Konto erstellen</a>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 12, letterSpacing: "0.08em" }}>
              Gregor Zwanzig · Wetter-Briefings · Headless
            </div>
          </div>

        </div>
      </div>
    </PhoneFrame>
  );
}

window.ScreenLoginMobile = ScreenLoginMobile;
