import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// A folha de tokens vem ANTES de todas: ela so declara, e as folhas seguintes passam a
// referenciar em vez de inventar. Ordem importa — declarar depois nao alcanca quem ja leu.
import "@/forge-tokens.css";
import "@/forge-primitivos.css";
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
import "@/workout-preview-density.css";
import "@/header-typography.css";
import "@/page-alignment.css";
import "@/workout-nutrition-actions.css";
import "@/home-reference-lock.css";
import "@/features/screen-polish.css";
// A folha do Inicio vem por ULTIMO: importada pelo componente, ela carregava ANTES das
// folhas daqui e perdia todo empate de especificidade para as camadas antigas.
import "@/features/forge-inicio.css";
import "@/features/forge-perfil.css";
// Referência visual oficial aprovada pelo Astra 6. Deve carregar por último.
import "@/astra-visual.css";

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
