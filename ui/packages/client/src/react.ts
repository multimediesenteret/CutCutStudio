import { createContext, useContext, useSyncExternalStore } from "react";
import type { Snapshot, Store } from "./store";
import type { Transport } from "./transport";

export interface Studio {
  store: Store;
  transport: Transport;
}

export const StudioContext = createContext<Studio | null>(null);

export function useStudio(): Studio {
  const ctx = useContext(StudioContext);
  if (!ctx) throw new Error("StudioContext missing");
  return ctx;
}

/** Subscribe to the store; re-render only when the selected value changes. */
export function useSnapshot<T>(select: (s: Snapshot) => T): T {
  const { store } = useStudio();
  return useSyncExternalStore(store.subscribe, () => select(store.getSnapshot()));
}
