"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, EventBatchIn } from "./api";

export type TelemetryEventType =
  | "shown"
  | "expanded"
  | "collapsed"
  | "replayed"
  | "hidden"
  | "visible"
  | "clarity_rated"
  | "dismissed";

export interface TelemetryEvent {
  idempotency_key: string;
  type: TelemetryEventType;
  client_ts: string;
  payload?: Record<string, unknown>;
}

export function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface UseExplanationTelemetryOptions {
  autoTrackVisibility?: boolean;
}

export function useExplanationTelemetry(
  explanationId: string | null | undefined,
  options: UseExplanationTelemetryOptions = {}
) {
  const { autoTrackVisibility = true } = options;
  const elementRef = useRef<HTMLDivElement | null>(null);

  const isVisibleRef = useRef<boolean>(false);
  const hasShownRef = useRef<boolean>(false);
  const queueRef = useRef<TelemetryEvent[]>([]);
  const isSendingRef = useRef<boolean>(false);

  const [activeDwellMs, setActiveDwellMs] = useState<number>(0);
  const dwellStartRef = useRef<number | null>(null);

  const storageKey = explanationId ? `pcg_telemetry_queue_${explanationId}` : null;

  // Load unsent events from localStorage on mount
  useEffect(() => {
    if (!storageKey || typeof window === "undefined") return;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          queueRef.current = [...parsed, ...queueRef.current];
        }
      }
    } catch {
      // Ignore localStorage parse errors
    }
  }, [storageKey]);

  const saveQueueToStorage = useCallback(() => {
    if (!storageKey || typeof window === "undefined") return;
    try {
      if (queueRef.current.length > 0) {
        localStorage.setItem(storageKey, JSON.stringify(queueRef.current));
      } else {
        localStorage.removeItem(storageKey);
      }
    } catch {
      // Ignore localStorage write quota errors
    }
  }, [storageKey]);

  const flushQueue = useCallback(async () => {
    if (!explanationId || queueRef.current.length === 0 || isSendingRef.current) {
      return;
    }

    isSendingRef.current = true;
    const batchToSend = [...queueRef.current];

    try {
      await api.explanations.sendEvents(
        explanationId,
        batchToSend as unknown as EventBatchIn["events"]
      );

      // Remove successfully sent events by matching idempotency keys
      const sentKeys = new Set(batchToSend.map((e) => e.idempotency_key));
      queueRef.current = queueRef.current.filter((e) => !sentKeys.has(e.idempotency_key));
      saveQueueToStorage();
    } catch {
      // Keep events in queue for retry on next interval
    } finally {
      isSendingRef.current = false;
    }
  }, [explanationId, saveQueueToStorage]);

  const recordEvent = useCallback(
    (type: TelemetryEventType, payload?: Record<string, unknown>) => {
      if (!explanationId) return;

      const event: TelemetryEvent = {
        idempotency_key: generateUUID(),
        type,
        client_ts: new Date().toISOString(),
        payload: payload || {},
      };

      queueRef.current.push(event);
      saveQueueToStorage();

      // Immediate flush for terminal events
      if (type === "dismissed") {
        void flushQueue();
      }
    },
    [explanationId, flushQueue, saveQueueToStorage]
  );

  // Interval dwell timer for local UI display
  useEffect(() => {
    const timer = setInterval(() => {
      if (isVisibleRef.current && dwellStartRef.current !== null) {
        const now = Date.now();
        setActiveDwellMs((prev) => prev + (now - dwellStartRef.current!));
        dwellStartRef.current = now;
      }
    }, 500);
    return () => clearInterval(timer);
  }, []);

  // Periodic batch transmission every 5 seconds
  useEffect(() => {
    if (!explanationId) return;
    const interval = setInterval(() => {
      void flushQueue();
    }, 5000);

    return () => clearInterval(interval);
  }, [explanationId, flushQueue]);

  // Handle visibility transitions: updating dwell tracking and logging events
  const handleVisibilityChange = useCallback(
    (inView: boolean, docVisible: boolean) => {
      const nowVisible = inView && docVisible;
      const wasVisible = isVisibleRef.current;

      if (nowVisible && !wasVisible) {
        isVisibleRef.current = true;
        dwellStartRef.current = Date.now();

        if (!hasShownRef.current) {
          hasShownRef.current = true;
          recordEvent("shown");
        } else {
          recordEvent("visible");
        }
      } else if (!nowVisible && wasVisible) {
        isVisibleRef.current = false;
        dwellStartRef.current = null;
        recordEvent("hidden");
      }
    },
    [recordEvent]
  );

  // IntersectionObserver + Page Visibility setup
  useEffect(() => {
    if (!autoTrackVisibility || !explanationId || typeof window === "undefined") {
      return;
    }

    const node = elementRef.current;
    if (!node) return;

    let inViewport = false;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        inViewport = entry.isIntersecting && entry.intersectionRatio >= 0.5;
        handleVisibilityChange(inViewport, document.visibilityState === "visible");
      },
      { threshold: [0, 0.5, 1.0] }
    );

    observer.observe(node);

    const onDocVisibilityChange = () => {
      handleVisibilityChange(inViewport, document.visibilityState === "visible");
    };

    document.addEventListener("visibilitychange", onDocVisibilityChange);

    // Send on pagehide via navigator.sendBeacon
    const onPageHide = () => {
      if (isVisibleRef.current) {
        recordEvent("hidden");
      }
      if (queueRef.current.length > 0 && typeof navigator !== "undefined" && navigator.sendBeacon) {
        const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/explanations/${explanationId}/events`;
        const blob = new Blob(
          [JSON.stringify({ events: queueRef.current })],
          { type: "application/json" }
        );
        navigator.sendBeacon(url, blob);
      }
    };

    window.addEventListener("pagehide", onPageHide);

    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", onDocVisibilityChange);
      window.removeEventListener("pagehide", onPageHide);
      if (isVisibleRef.current) {
        recordEvent("hidden");
        isVisibleRef.current = false;
      }
      void flushQueue();
    };
  }, [autoTrackVisibility, explanationId, flushQueue, handleVisibilityChange, recordEvent]);

  return {
    ref: elementRef,
    activeDwellMs,
    recordEvent,
    trackExpanded: () => recordEvent("expanded"),
    trackCollapsed: () => recordEvent("collapsed"),
    trackReplayed: () => recordEvent("replayed"),
    trackClarityRated: (rating: number) => recordEvent("clarity_rated", { rating }),
    trackDismissed: () => recordEvent("dismissed"),
    flush: flushQueue,
  };
}
