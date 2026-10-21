// Pure translation from atem-connection state to the `atem.state` payload that CutCut core
// reads (docs/plans/devices-companion-atem.md). No decisions here: the bridge only reports.
// The payload uses ATEM input numbers; core maps them to C1, BIRD, LAPTOP … from the studio
// setup, so the bridge never needs to know the studio (ADR-0012).
import { Enums, type AtemState } from "atem-connection";

export const MP1 = 3010;
export const MP2 = 3020;
export const SUPERSOURCE = 6000;

/** Multiview window source as named in CutCut's rutekart (spec 6.1). */
export function sourceName(id: number | undefined): string {
  if (id === undefined) return "other";
  if (id >= 1 && id <= 8) return `input${id}`;
  switch (id) {
    case 0:
      return "black";
    case 1000:
      return "colorbars";
    case MP1:
      return "mediaplayer1";
    case MP2:
      return "mediaplayer2";
    case SUPERSOURCE:
      return "supersource";
    case 10010:
      return "program";
    case 10011:
      return "preview";
    default:
      return "other"; // e.g. recording status; confirmed in the machine test (DA-5)
  }
}

export interface MultiviewPayload {
  layout: "2+8" | "other";
  preview_left: boolean;
  windows: string[];
  safe_area: boolean;
  audio_meters: boolean;
  tally: boolean;
  video_mode: string;
}

export interface MacroPayload {
  /** Numbered as in ATEM Software Control and Companion: the first macro is 1. */
  number: number;
  name: string;
}

export interface AtemStatePayload {
  connected: true;
  model: string;
  program_input: number;
  preview_input: number;
  multiview: MultiviewPayload | null;
  recording: string | null;
  macros: MacroPayload[];
}

/** The macros stored in the ATEM, for the layout check at start-up (DA-7, spec 7.2). */
export function macros(state: AtemState): MacroPayload[] {
  const list = state.macro?.macroProperties ?? [];
  const out: MacroPayload[] = [];
  list.forEach((m, i) => {
    if (m?.isUsed) out.push({ number: i + 1, name: m.name });
  });
  return out;
}

function videoMode(state: AtemState): string {
  const name = Enums.VideoMode[state.settings.videoMode] ?? "unknown";
  return name.replace(/^[NP]/, ""); // "P1080p50" → "1080p50"
}

export function multiview(state: AtemState): MultiviewPayload | null {
  const mv = state.settings.multiViewers[0];
  if (!mv) return null;
  const layout = mv.properties?.layout ?? Enums.MultiViewerLayout.Default;
  const twoPlusEight =
    layout === Enums.MultiViewerLayout.Default || layout === Enums.MultiViewerLayout.ProgramTop;
  const small = mv.windows.slice(2, 10);
  return {
    layout: twoPlusEight ? "2+8" : "other",
    // ATEM's default is preview left, program right; «swap» puts program left.
    preview_left: !(mv.properties?.programPreviewSwapped ?? false),
    windows: Array.from({ length: 8 }, (_, i) => sourceName(small[i]?.source)),
    safe_area: mv.windows.some((w) => w?.safeTitle === true),
    audio_meters: mv.windows.some((w) => w?.audioMeter === true),
    tally: mv.windows.every((w) => w?.overlayProperties?.borderVisible !== false),
    video_mode: videoMode(state),
  };
}

export function statePayload(state: AtemState): AtemStatePayload {
  const me = state.video.mixEffects[0];
  return {
    connected: true,
    model: Enums.Model[state.info.model] ?? "Unknown",
    program_input: me?.programInput ?? 0,
    preview_input: me?.previewInput ?? 0,
    multiview: multiview(state),
    recording: state.recording?.status?.state !== undefined
      ? (Enums.RecordingStatus[state.recording.status.state] ?? null)
      : null,
    macros: macros(state),
  };
}
