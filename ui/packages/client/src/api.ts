// Typed command helpers over the transport (spec 10.1). One place for every call the screens make.
import type { components } from "./api-types";
import type { Transport } from "./transport";

export type Preset = "rolig" | "standard" | "energisk";
export type Role = "touch" | "operator" | "admin";

export interface RulesDetail {
  preset: Preset;
  values: Record<string, number | boolean>;
  preset_values: Record<string, number | boolean>;
  overrides: Record<string, number>;
  limits: Record<string, { type: string; min: number | null; max: number | null }>;
  ids: string[];
}

export interface SessionRow {
  session_id: string;
  username: string;
  display_name: string;
  started_at: string;
  ended_at: string | null;
  duration_s: number;
  recording: string | null;
  started_by: string | null;
  stopped_by: string | null;
  participants: number;
  video: boolean;
  publish: string | null;
}

export interface CameraConfig {
  driver: string;
  ip?: string | null;
  atem_input: number;
  role?: string;
}

export interface ShowDetail {
  id: string;
  name: string;
  cameras: Record<string, CameraConfig>;
  participants: { id: string; name: string; mic: string; camera: string; role: string }[];
}

export function commands(t: Transport) {
  return {
    setShow: (guests: number, video: boolean, laptop = false) =>
      t.send("PUT", "/api/session/show", { guests, video, laptop }),
    startRecording: () => t.send("POST", "/api/recording", { action: "start" }),
    stopRecording: () => t.send("POST", "/api/recording", { action: "stop" }),
    logout: () => t.send("DELETE", "/api/session"),
    help: () => t.send("POST", "/api/help"),
    /** P12: «Bytt i CutCut», «Vi bytter plass» or ignore. */
    seatCheck: (action: "swap" | "moved" | "ignore") =>
      t.send("POST", "/api/seat-check", { action }),
    touched: () => t.send("POST", "/api/touch/touched"),
    again: () => t.send("POST", "/api/touch/again"),
    startWithoutCard: () => t.send("POST", "/api/touch/start"),
    heartbeat: () => t.send("POST", "/api/touch/heartbeat"),
    setLoginMode: (mode: "open" | "card") => t.send("PUT", "/api/settings/login", { mode }),
    startSession: (username: string, displayName?: string) =>
      t.send("POST", "/api/session", { username, display_name: displayName }),
    touchStep: (step: string) => t.send("POST", "/api/touch/step", { step }),
    auto: (on: boolean) => t.send("POST", "/api/auto", { on }),
    lock: (on: boolean) => t.send("POST", "/api/lock", { on }),
    cut: (shot: string) => t.send("POST", "/api/cut", { shot }),
    preview: (shot: string) => t.send("POST", "/api/preview", { shot }),
    content: (enabled: boolean) => t.send("POST", "/api/content", { enabled }),
    preset: (preset: Preset) => t.send("POST", "/api/preset", { preset }),
    overrides: (changes: Record<string, number | null>) =>
      t.send("POST", "/api/rules/overrides", changes),
    rules: () => t.get<RulesDetail>("/api/rules"),
    me: () => t.get<{ role: Role; actor: string }>("/api/me"),
    log: (since = 0) => t.get<components["schemas"]["Decision"][]>(`/api/log?since=${since}`),
    sessions: (days = 1) => t.get<SessionRow[]>(`/api/sessions?days=${days}`),
    show: (id: string) => t.get<ShowDetail>(`/api/shows/${encodeURIComponent(id)}`),
    features: (changes: Record<string, boolean | "off" | "shadow" | "on">) =>
      t.send("POST", "/api/features", changes),
    shadow: (on: boolean) => t.send("POST", "/api/shadow", { on }),
    ack: (alertId: number) => t.send("POST", `/api/alerts/${alertId}/ack`),
    morningCheck: () => t.send("POST", "/api/health/morning-check"),
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
