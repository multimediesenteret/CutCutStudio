// Oppsett → steg 6: how the multiview gets into the PC (D-071). The INOGENI 4KXUSB3 on the
// ATEM's multiview output, or the ATEM's own webcam output over USB-C with Multi View chosen.
// The video layer switches device without a restart, and the engine allows for the delay.
import { errorMessage, useStudio } from "@cutcut/client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { type Ctx } from "../lib";

export interface CaptureMethod {
  value: "inogeni" | "atem_usb";
  label: string;
  device_name: string;
  delay_ms: number | null; // measured with hwtest vision (V4)
  assumed_delay_ms: number;
}

export interface VideoInfo {
  kind: "uvc" | "none";
  method: CaptureMethod["value"];
  method_overridden: boolean;
  file_method: string;
  name: string;
  name_used: string;
  methods: CaptureMethod[];
  delay_ms: number;
  measured: boolean;
}

const HOW: Record<CaptureMethod["value"], string[]> = {
  inogeni: [
    "ATEM-ens multiview-utgang (HDMI) til INOGENI 4KXUSB3.",
    "INOGENI i en USB 3-port rett på hovedkortet (ikke via hub).",
    "Ukomprimert bilde; multiview-utgangen er opptatt av INOGENI.",
  ],
  atem_usb: [
    "USB-C fra ATEM-en til en USB 3-port på PC-en, med en USB-C 3.1-kabel (kort, under 3 m).",
    "ATEM Software Control: Output → Webcam Out → Multi View.",
    "Ingen ekstra boks, og multiview-utgangen blir ledig for en skjerm. Sjekk at ISO-opptaket virker samtidig.",
  ],
};

export function Capture({ ctx }: { ctx: Ctx }) {
  const { transport } = useStudio();
  const [v, setV] = useState<VideoInfo | null>(null);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const admin = ctx.role === "admin";

  const load = useCallback(() => {
    transport
      .get<{ video?: VideoInfo }>("/api/settings/devices")
      .then((i) => {
        setV(i.video ?? null);
        setName(i.video?.name ?? "");
      })
      .catch(() => setV(null));
  }, [transport]);
  useEffect(load, [load]);

  if (!v) return null;
  const send = (body: Record<string, string | null>) => {
    setMsg(null);
    transport
      .send("PUT", "/api/settings/devices", body)
      .then(load)
      .catch((x: unknown) => setMsg(errorMessage(x)));
  };
  const choose = (m: CaptureMethod["value"]) => {
    if (m === v.method) return;
    // the file's method is the default: choosing it removes the override
    send({ "video.method": m === v.file_method ? null : m, "video.name": null });
  };
  const saveName = (e: FormEvent) => {
    e.preventDefault();
    send({ "video.name": name.trim() || null });
  };
  const current = v.methods.find((m) => m.value === v.method);

  return (
    <div className="panel">
      <div className="ph">
        <span className="lbl">Multiview-capture · hvordan bildet kommer inn i PC-en</span>
        <span className="hst">
          <i />
          {current?.label ?? v.method}
        </span>
      </div>
      <div className="seg" role="group" aria-label="Multiview capture-metode">
        {v.methods.map((m) => (
          <button
            key={m.value}
            type="button"
            className={m.value === v.method ? "sel" : ""}
            aria-pressed={m.value === v.method}
            disabled={!admin}
            onClick={() => choose(m.value)}
          >
            {m.label}
          </button>
        ))}
      </div>
      <ul className="small" style={{ marginTop: 8 }}>
        {HOW[v.method].map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <div className="kv" style={{ marginTop: 10 }}>
        <span>Enhet i Windows</span>
        <span className="mono small">«{v.name_used}»</span>
        {v.methods.map((m) => (
          <FragmentRow key={m.value} m={m} active={m.value === v.method} />
        ))}
      </div>
      <p className="muted small">
        Videolaget bytter enhet med en gang, uten omstart. Motoren venter på bildet så lenge
        forsinkelsen tilsier. Mål forsinkelsen med{" "}
        <span className="mono">cutcut hwtest vision</span> (V4); den målte verdien lagres for
        metoden og brukes i stedet for utgangspunktet. Begge metodene kan testes uten å bytte her:{" "}
        <span className="mono">--metode atem_usb</span>.
      </p>
      {admin && (
        <details>
          <summary>Annet enhetsnavn</summary>
          <form className="row" onSubmit={saveName}>
            <input
              className="addr"
              aria-label="Enhetsnavn i Windows"
              value={name}
              placeholder={current?.device_name ?? ""}
              onChange={(e) => setName(e.target.value)}
            />
            <button className="btn" type="submit" disabled={name.trim() === v.name.trim()}>
              Lagre
            </button>
          </form>
          <p className="muted small">
            Bare hvis Windows kaller enheten noe annet (del av navnet holder). Tomt = «
            {current?.device_name}».
          </p>
        </details>
      )}
      {!admin && <p className="muted small">Bare admin kan bytte metode.</p>}
      {msg && <p className="err-text small">{msg}</p>}
    </div>
  );
}

function FragmentRow({ m, active }: { m: CaptureMethod; active: boolean }) {
  const delay =
    m.delay_ms !== null ? `${m.delay_ms} ms, målt` : `${m.assumed_delay_ms} ms, utgangspunkt`;
  return (
    <>
      <span>{m.value === "inogeni" ? "INOGENI" : "ATEM USB-C"}</span>
      <span>
        Forsinkelse {delay}
        {active ? " · i bruk" : ""}
      </span>
    </>
  );
}
