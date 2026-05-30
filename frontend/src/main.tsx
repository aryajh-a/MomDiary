import { ClerkProvider, useAuth } from "@clerk/clerk-react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, useNavigate } from "react-router-dom";
import App from "./App";
import { setTokenProvider } from "@/shared/apiClient";
import "./styles/tailwind.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
if (!PUBLISHABLE_KEY) {
  throw new Error(
    "VITE_CLERK_PUBLISHABLE_KEY is not set. Copy frontend/.env.example to frontend/.env and provide the Clerk publishable key.",
  );
}

/**
 * Registers the Clerk JWT token provider with the apiClient on mount, and
 * unregisters on unmount / sign-out. This is the single bridge between
 * Clerk's React context and the imperative `fetch`-based apiClient.
 */
function ClerkTokenBridge(): null {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setTokenProvider(null);
      return;
    }
    setTokenProvider(() => getToken({ template: "momdiary-default" }));
    return () => setTokenProvider(null);
  }, [isLoaded, isSignedIn, getToken]);
  return null;
}

/**
 * Forwards Clerk's redirect callbacks through react-router so post-sign-in
 * navigation stays SPA-internal.
 */
function ClerkRouted(props: { children: React.ReactNode }): JSX.Element {
  const navigate = useNavigate();
  return (
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      routerPush={(to: string) => navigate(to)}
      routerReplace={(to: string) => navigate(to, { replace: true })}
    >
      <ClerkTokenBridge />
      {props.children}
    </ClerkProvider>
  );
}

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("#root element not found");

createRoot(rootEl).render(
  <StrictMode>
    <BrowserRouter>
      <ClerkRouted>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </ClerkRouted>
    </BrowserRouter>
  </StrictMode>,
);
