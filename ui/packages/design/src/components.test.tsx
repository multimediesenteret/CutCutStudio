import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HoldButton, LevelBar, MicRow, SeatButton, levelFromDb } from "./components";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance"] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function hold() {
  const done = vi.fn();
  render(
    <HoldButton label="Hold inne for å avslutte" onComplete={done}>
      Avslutt
    </HoldButton>,
  );
  return { done, button: screen.getByRole("button", { name: "Hold inne for å avslutte" }) };
}

describe("HoldButton", () => {
  it("fires after holding for 2 s", () => {
    const { done, button } = hold();
    fireEvent.pointerDown(button, { pointerId: 1 });
    act(() => vi.advanceTimersByTime(1900));
    expect(done).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(200));
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("does nothing when let go early", () => {
    const { done, button } = hold();
    fireEvent.pointerDown(button, { pointerId: 1 });
    act(() => vi.advanceTimersByTime(1500));
    fireEvent.pointerUp(button, { pointerId: 1 });
    act(() => vi.advanceTimersByTime(3000));
    expect(done).not.toHaveBeenCalled();
  });

  it("works from the keyboard", () => {
    const { done, button } = hold();
    fireEvent.keyDown(button, { key: "Enter" });
    act(() => vi.advanceTimersByTime(2100));
    expect(done).toHaveBeenCalledTimes(1);
  });
});

describe("meters and seats", () => {
  it("maps dB to 0–1 and clamps", () => {
    expect(levelFromDb(-60)).toBe(0);
    expect(levelFromDb(-12)).toBe(1);
    expect(levelFromDb(-31)).toBeCloseTo(0.5, 2);
  });

  it("draws the level as a CSS variable, not width", () => {
    const { container } = render(<LevelBar level={0.37} />);
    const bar = container.querySelector(".cc-level") as HTMLElement;
    expect(bar.style.getPropertyValue("--lv")).toBe("0.38");
  });

  it("marks a talking, muted mic", () => {
    const { container } = render(
      <MicRow index={1} title="Gjest 1" subtitle="snakker" level={0.5} talking muted={false} />,
    );
    expect(container.querySelector(".cc-mic")?.className).toBe("cc-mic talk");
  });

  it("the presenter seat cannot be turned off", () => {
    const press = vi.fn();
    render(
      <SeatButton index={0} title="Programleder" subtitle="ved mikseren" on lead onPress={press} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(press).not.toHaveBeenCalled();
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("true");
  });
});
