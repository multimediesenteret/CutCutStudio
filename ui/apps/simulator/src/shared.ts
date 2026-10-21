// One replay shared by the front page and both screens. The screens run in iframes (so their
// styles stay apart, as in the studio) and borrow the store and transport from the page.
import { ReplayTransport, Store, type Trace } from "@cutcut/client";

export interface StoryInfo {
  id: string;
  title: string;
  file: string;
}

export interface Sim {
  store: Store;
  transport: ReplayTransport;
  story: StoryInfo;
  stories: StoryInfo[];
}

declare global {
  interface Window {
    cutcutSim?: Sim;
  }
}

const BASE = import.meta.env.BASE_URL;

async function json<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`Fant ikke ${path}`);
  return (await res.json()) as T;
}

export async function loadStories(): Promise<StoryInfo[]> {
  return json<StoryInfo[]>("traces/index.json");
}

export async function startSim(stories: StoryInfo[], id?: string): Promise<Sim> {
  const story = stories.find((s) => s.id === id) ?? stories[0];
  if (!story) throw new Error("Ingen forløp");
  const trace = await json<Trace>(`traces/${story.file}`);
  const store = new Store();
  const transport = new ReplayTransport(trace);
  transport.start(store);
  return { store, transport, story, stories };
}

/** In an iframe: the page's replay. Opened on its own: a replay of the first story. */
export async function simForScreen(): Promise<Pick<Sim, "store" | "transport">> {
  try {
    const parent = window.parent !== window ? window.parent.cutcutSim : undefined;
    if (parent) return parent;
  } catch {
    /* another origin: run on our own */
  }
  const id = new URLSearchParams(location.search).get("story") ?? undefined;
  return startSim(await loadStories(), id);
}
