import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";
import "@/typography-premium.css";
import "@/reference-home.css";
import "@/reference-platform.css";
import "@/reference-platform-extra.css";
import "@/performance-pass.css";
import "@/iron-ledger-pass-01.css";
import "@/iron-ledger-pass-02.css";
import "@/mobile-premium.css";
import "@/magic-patterns-v2.css";
import "@/reference-exact-v3.css";
import "@/progress-fix.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="loading">Carregando FORGE...</div>}>
        <App />
      </Suspense>
    </QueryClientProvider>
  </React.StrictMode>,
);
