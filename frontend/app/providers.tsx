"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { SWRConfig } from "swr";

// ── WebSocket context ─────────────────────────────────────────────────────────

const WebSocketContext = createContext<WebSocket | null>(null);

export function useWebSocket(): WebSocket | null {
  return useContext(WebSocketContext);
}

function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connection deferred until an agent token is available; stub for now.
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return (
    <WebSocketContext.Provider value={wsRef.current}>
      {children}
    </WebSocketContext.Provider>
  );
}

// ── Root providers ────────────────────────────────────────────────────────────

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      <WebSocketProvider>{children}</WebSocketProvider>
    </SWRConfig>
  );
}
