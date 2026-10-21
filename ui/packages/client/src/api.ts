// Typed command helpers over the transport (spec 10.1). One place for every call the screens make.
import type { Transport } from "./transport";

export type Preset = "rolig" | "standard" | "energisk";

export function commands(t: Transport) {
  return {
    setShow: (guests: number, video: boolean, laptop = false) =>
      t.send("PUT", "/api/session/show", { guests, video, laptop }),
    startRecording: () => t.send("POST", "/api/recording", { action: "start" }),
    stopRecording: () => t.send("POST", "/api/recording", { action: "stop" }),
    logout: () => t.send("DELETE", "/api/session"),
    help: () => t.send("POST", "/api/help"),
    touched: () => t.send("POST", "/api/touch/touched"),
    startSession: (username: string, displayName?: string) =>
      t.send("POST", "/api/session", { username, display_name: displayName }),
    touchStep: (step: string) => t.send("POST", "/api/touch/step", { step }),
    auto: (on: boolean) => t.send("POST", "/api/auto", { on }),
    lock: (on: boolean) => t.send("POST", "/api/lock", { on }),
    cut: (shot: string) => t.send("POST", "/api/cut", { shot }),
    preview: (shot: string) => t.send("POST", "/api/preview", { shot }),
    content: (enabled: boolean) => t.send("POST", "/api/content", { enabled }),
    preset: (preset: Preset) => t.send("POST", "/api/preset", { preset }),
    features: (changes: Record<string, boolean>) => t.send("POST", "/api/features", changes),
    shadow: (on: boolean) => t.send("POST", "/api/shadow", { on }),
    ack: (alertId: number) => t.send("POST", `/api/alerts/${alertId}/ack`),
    login: (username: string, pin: string) => t.send("POST", "/api/login", { username, pin }),
    techLogout: () => t.send("POST", "/api/logout"),
    // simulator only (cutcut sim / Vercel)
    simCard: (card: string) => t.send("POST", "/api/sim/card", { card }),
    simTalk: (participant: string, on: boolean) =>
      t.send("POST", "/api/sim/talk", { participant, on }),
    simConversation: (on: boolean) => t.send("POST", "/api/sim/conversation", { on }),
    simContent: (state: string | null) => t.send("POST", "/api/sim/content", { state }),
    simLaptopAudio: (on: boolean) => t.send("POST", "/api/sim/laptop-audio", { on }),
    simFault: (kind: string, on: boolean, camera?: string) =>
      t.send("POST", "/api/sim/fault", { kind, on, camera }),
  };
}

export type Commands = ReturnType<typeof commands>;
