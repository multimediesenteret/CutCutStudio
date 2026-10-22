// Contract test (DA-1): the payload the bridge sends for a known ATEM state. The same JSON is
// read by core's tests (tests/integration/test_atem_bridge.py), so both sides agree.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { Enums, type AtemState } from "atem-connection";
import { describe, expect, it } from "vitest";
import { parseCommand } from "./bus.ts";
import { MP1, sourceName, statePayload } from "./translate.ts";

const FIXTURE = resolve(import.meta.dirname, "../../../tests/fixtures/atem/state-studio.json");

/** The studio as in the multiview photo (D-053): MP1 on program, Camera 1 on preview. */
function studioState(): AtemState {
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
    video: { mixEffects: [{ programInput: MP1, previewInput: 1 }], auxilliaries: [10010, 6] },
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
    recording: {
      status: {
        state: Enums.RecordingStatus.Idle,
        error: Enums.RecordingError.None,
        recordingTimeAvailable: 5400,
      },
      properties: {
        filename: "",
        workingSet1DiskId: 1,
        workingSet2DiskId: 0,
        recordInAllCameras: true,
      },
      disks: {
        1: {
          diskId: 1,
          volumeName: "ISO-SSD",
          recordingTimeAvailable: 5400,
          status: Enums.RecordingDiskStatus.Active,
        },
      },
    },
    inputs: {
      1: { inputId: 1, shortName: "CAM1", longName: "Camera 1" },
      2: { inputId: 2, shortName: "CAM2", longName: "Camera 2" },
      6: { inputId: 6, shortName: "CAM6", longName: "Camera 6" },
    },
    macro: {
      // ATEM index 9 is macro 10 in ATEM Software Control. 39 = 40 is missing on purpose.
      macroProperties: Object.assign([], {
        9: { name: "PIP_P1_CONTENT", description: "", isUsed: true },
        19: { name: "PIP_P1_P2", description: "", isUsed: true },
        29: { name: "QUAD4", description: "", isUsed: true },
        30: { name: "old", description: "", isUsed: false },
      }),
    },
  } as unknown as AtemState;
}

describe("atem.state payload", () => {
  it("matches the shared contract fixture", () => {
    const payload = statePayload(studioState());
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

  it("numbers macros like ATEM Software Control (1-based) and skips empty slots", () => {
    expect(statePayload(studioState()).macros).toEqual([
      { number: 10, name: "PIP_P1_CONTENT" },
      { number: 20, name: "PIP_P1_P2" },
      { number: 30, name: "QUAD4" },
    ]);
  });

  it("names multiview sources like the rutekart", () => {
    expect(sourceName(6000)).toBe("supersource");
    expect(sourceName(3020)).toBe("mediaplayer2");
    expect(sourceName(undefined)).toBe("other");
  });

  it("reports a swapped preview/program and a non 2+8 layout", () => {
    const s = studioState();
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
    // setup step 3, «Fiks for meg»: ATEM limits long names to 20 and short names to 4
    const name = { input: 6, long: "LAPTOP", short: "LAPT" };
    expect(parseCommand({ id: "e", op: "input_name", args: name })?.args).toEqual(name);
    expect(
      parseCommand({ id: "f", op: "input_name", args: { ...name, short: "LAPTOP" } }),
    ).toBeNull();
    expect(parseCommand({ id: "g", op: "input_name", args: { input: 6 } })).toBeNull();
    // ISO (7.7): a file name the ATEM accepts, nothing that could be a path
    const file = "2026-10-22_podcast_ola";
    expect(parseCommand({ id: "h", op: "iso_start", args: { filename: file } })?.args).toEqual({
      filename: file,
    });
    expect(parseCommand({ id: "i", op: "iso_start", args: { filename: "../x" } })).toBeNull();
    expect(parseCommand({ id: "j", op: "iso_stop" })?.op).toBe("iso_stop");
  });
});
