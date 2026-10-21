// Shared helpers for the technician window.
import {
  errorMessage,
  type Commands,
  type Decision,
  type Role,
  type StudioState,
} from "@cutcut/client";
import type { IconName } from "@cutcut/design";

export type View =
  "oversikt" | "regi" | "kameraer" | "opptak" | "helse" | "oppsett" | "logg" | "innstillinger";

/** Menu per role (D-045): operator sees five pages, admin also Regi, Oppsett, Innstillinger. */
export const NAV: { view: View; label: string; title: string; icon: IconName; admin: boolean }[] = [
  { view: "oversikt", label: "Oversikt", title: "Oversikt", icon: "grid", admin: false },
  { view: "regi", label: "Regi", title: "Regi og brytere", icon: "sliders", admin: true },
  { view: "kameraer", label: "Kameraer", title: "Kameraer", icon: "cam", admin: false },
  { view: "opptak", label: "Opptak", title: "Opptak", icon: "rec", admin: false },
  { view: "helse", label: "Helse", title: "Helse", icon: "pulse", admin: false },
  { view: "oppsett", label: "Oppsett", title: "Oppsett-veiviser", icon: "wand", admin: true },
  { view: "logg", label: "Logg", title: "Beslutningslogg", icon: "list", admin: false },
  {
    view: "innstillinger",
    label: "Innstill.",
    title: "Innstillinger",
    icon: "gear",
    admin: true,
  },
];

export function allowed(view: View, role: Role): boolean {
  const item = NAV.find((n) => n.view === view);
  if (!item || role === "touch") return false;
  return !item.admin || role === "admin";
}

export interface Ctx {
  state: StudioState;
  cmd: Commands;
  role: Role;
  /** Run a command; a refusal is shown as a toast with the server's Norwegian message. */
  run: (p: Promise<unknown>) => void;
  toast: (text: string) => void;
  go: (view: View) => void;
}

const CAM_OF: Record<string, string> = { P1: "1", P2: "2", P3: "3", P4: "4" };

/** «CAM 2 · Gjest 1», «CAM 5 · Fugleperspektiv», «IN 6 · Laptop» (D-041 display names). */
export function shotName(state: StudioState, shot: string | null | undefined): string {
  if (!shot) return "–";
  if (shot === "BIRD") return "CAM 5 · Fugleperspektiv";
  if (shot === "WIDE") return "CAM 7 · Halvtotal";
  if (shot === "CONTENT") return "IN 6 · Laptop";
  if (shot === "AUDIO_ONLY") return "Kun lyd-grafikk";
  if (shot.startsWith("CU:")) {
    const id = shot.slice(3);
    const p = state.participants.find((x) => x.id === id);
    return `CAM ${CAM_OF[id] ?? "?"} · ${p?.name ?? id}`;
  }
  return shot.replace(/^PIP:/, "PiP ").replace("+CONTENT", " + laptop");
}

/** Which multiview tile a shot lives on, if any. */
export function tileOf(shot: string | null | undefined): string | null {
  if (!shot) return null;
  if (shot.startsWith("CU:")) return shot.slice(3);
  if (shot === "BIRD" || shot === "CONTENT") return shot;
  return null;
}

export function shotColor(shot: string | null | undefined): string {
  const t = tileOf(shot);
  if (t && t.startsWith("P")) return `var(--${t.toLowerCase()})`;
  if (t === "BIRD") return "var(--wait)";
  if (t === "CONTENT") return "var(--eye)";
  return "var(--bleed)";
}

export function isCut(d: Decision): boolean {
  return d.action === "cut";
}

export function isError(d: Decision): boolean {
  return (d.rule ?? "").startsWith("S");
}

export function ruleLabel(rule: string | null | undefined): string {
  if (!rule) return "";
  return rule === "MANUAL" ? "manuell" : rule;
}

/** 14:02:11 from an ISO timestamp, in local time. */
export function hms(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "" : d.toTimeString().slice(0, 8);
}

export function errorText(e: unknown): string {
  return errorMessage(e);
}
