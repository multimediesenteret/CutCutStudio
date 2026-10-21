// Contract test (DA-1): the payload the bridge sends for a known ATEM state. The same JSON is
// read by core's tests (tests/integration/test_atem_bridge.py), so both sides agree.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { Enums, type AtemState } from "atem-connection";
import { describe, expect, it } from "vitest";
import { parseCommand } from "./bus.ts";
import { MP1, sourceName, statePayload } from "./translate.ts";

const FIXTURE = resolve(import.meta.dirname, "../../../tests/fixtures/atem/state-ntnu.json");

/** The NTNU studio as in the multiview photo (D-053): MP1 on program, Camera 1 on preview. */
function ntnuState(): AtemState {
  const win = (source: number, extra: object = {}) => ({
    source,
    windowIndex: 0,
    supportsVuMeter: true,
    supportsSafeArea: true,
    overlayProperties: { labelVisible: true, borderVisible: true },
    ...extra,
  });
  return {
    info: { model: Enums.Model.TelevisionStudioHD8ISO },
    video: { mixEffects: [{ programInput: MP1, previewInput: 1 }] },
    settings: {
      videoMode: Enums.VideoMode.P1080p50,
      multiViewers: [
        {
          index: 0,
          properties: { layout: Enums.MultiViewerLayout.Default, programPreviewSwapped: false },
          windows: [
            win(10011, { safeTitle: true }),
            win(10010),
            win(1),
            win(2),
            win(3),
            win(4),
            win(6),
            win(7),
            win(MP1),
            win(9001),
          ],
        },
      ],
    },
    recording: { status: { state: Enums.RecordingStatus.Idle } },
  } as unknown as AtemState;
}

describe("atem.state payload", () => {
  it("matches the shared contract fixture", () => {
    const payload = statePayload(ntnuState());
    const text = JSON.stringify(payload, null, 2) + "\n";
    if (process.env.UPDATE_FIXTURES) writeFileSync(FIXTURE, text);
    expect(text).toBe(readFileSync(FIXTURE, "utf8"));
    expect(payload.model).toBe("TelevisionStudioHD8ISO");
    expect(payload.multiview?.windows).toEqual([
      "input1",
      "input2",
      "input3",
      "input4",
      "input6",
      "input7",
      "mediaplayer1",
      "other",
    ]);
  });

  it("names multiview sources like the rutekart", () => {
    expect(sourceName(6000)).toBe("supersource");
    expect(sourceName(3020)).toBe("mediaplayer2");
    expect(sourceName(undefined)).toBe("other");
  });

  it("reports a swapped preview/program and a non 2+8 layout", () => {
    const s = ntnuState();
    const mv = s.settings.multiViewers[0] as unknown as {
      properties: { layout: number; programPreviewSwapped: boolean };
    };
    mv.properties.programPreviewSwapped = true;
    mv.properties.layout = Enums.MultiViewerLayout.ProgramLeft;
    const p = statePayload(s);
    expect(p.multiview?.preview_left).toBe(false);
    expect(p.multiview?.layout).toBe("other");
  });
});

describe("atem.cmd", () => {
  it("accepts only well-formed commands", () => {
    expect(parseCommand({ id: "a", op: "cut", args: { input: 2 } })).toEqual({
      id: "a",
      op: "cut",
      args: { input: 2 },
    });
    expect(parseCommand({ id: "b", op: "cut", args: { input: "2" } })).toBeNull();
    expect(parseCommand({ id: "c", op: "format_disk" })).toBeNull();
    expect(parseCommand(null)).toBeNull();
    expect(parseCommand({ id: "d", op: "run_macro", args: { macro: 40 } })?.args.macro).toBe(40);
  });
});
