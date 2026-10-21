import { useSnapshot } from "@cutcut/client";
import { Logo } from "@cutcut/design";

/** Placeholder shell (U-1). The real screens come in the following deliverables. */
export function App() {
  const connection = useSnapshot((s) => s.connection);
  return (
    <main style={{ padding: 32, fontFamily: "var(--f-ui)" }}>
      <Logo />
      <p>Teknikerskjerm – {connection === "connected" ? "tilkoblet" : "kobler til …"}</p>
    </main>
  );
}
