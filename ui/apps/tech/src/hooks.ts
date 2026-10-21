import { useSnapshot, type Commands, type Decision, type RulesDetail } from "@cutcut/client";
import { useEffect, useMemo, useState } from "react";

/** Decisions newest first: the live stream, backfilled once from the server's recent log. */
export function useDecisions(cmd: Commands): Decision[] {
  const live = useSnapshot((s) => s.decisions);
  const [earlier, setEarlier] = useState<Decision[]>([]);
  useEffect(() => {
    let alive = true;
    cmd
      .log(0)
      .then((list) => alive && setEarlier([...list].reverse()))
      .catch(() => undefined); // replay or offline: the live stream is enough
    return () => {
      alive = false;
    };
  }, [cmd]);
  return useMemo(() => {
    const seen = new Set(live.map((d) => `${d.mono_ms}|${d.correlation_id}`));
    return [...live, ...earlier.filter((d) => !seen.has(`${d.mono_ms}|${d.correlation_id}`))];
  }, [live, earlier]);
}

/** Rule values for the current preset and tuning; refetched when either changes. */
export function useRules(cmd: Commands, key: string): RulesDetail | null {
  const [rules, setRules] = useState<RulesDetail | null>(null);
  useEffect(() => {
    let alive = true;
    cmd
      .rules()
      .then((r) => alive && setRules(r))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [cmd, key]);
  return rules;
}
