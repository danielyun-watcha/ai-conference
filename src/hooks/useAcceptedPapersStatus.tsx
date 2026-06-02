import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export interface AcceptedPapersStatus {
  conference_id: string;
  title: string;
  year: number;
  url: string;
  released: boolean;
  detected_at: string | null;
  last_checked_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
}

type StatusMap = Map<string, AcceptedPapersStatus>;

interface StatusContextValue {
  statuses: StatusMap;
  loading: boolean;
  error: string | null;
}

const StatusContext = createContext<StatusContextValue>({
  statuses: new Map(),
  loading: false,
  error: null,
});

const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ||
  "http://localhost:8005";

export function AcceptedPapersStatusProvider({ children }: { children: ReactNode }) {
  const [statuses, setStatuses] = useState<StatusMap>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    fetch(`${BACKEND_URL}/api/accepted-papers/status`, {
      signal: controller.signal,
    })
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = (await resp.json()) as AcceptedPapersStatus[];
        if (cancelled) return;
        const map: StatusMap = new Map();
        for (const s of data) map.set(s.conference_id, s);
        setStatuses(map);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        // Backend is optional — frontend still renders without badges
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  return (
    <StatusContext.Provider value={{ statuses, loading, error }}>
      {children}
    </StatusContext.Provider>
  );
}

/** Get the release status for a conference by id, or undefined if not monitored. */
export function useAcceptedPapersStatus(conferenceId: string | undefined): AcceptedPapersStatus | undefined {
  const { statuses } = useContext(StatusContext);
  if (!conferenceId) return undefined;
  return statuses.get(conferenceId);
}
