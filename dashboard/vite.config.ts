// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Endereço do servidor Flask do projeto SIAT (control/server.py).
// Ajuste aqui se o Flask rodar em outra porta/IP (ex: acessando de outro dispositivo na rede).
const FLASK_API_URL = "http://localhost:5000";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    server: {
      // Em desenvolvimento, o React (Vite) roda numa porta e o Flask noutra.
      // Esse proxy faz fetch("/dados/...") no dashboard ser encaminhado para o Flask,
      // sem precisar mudar nenhum caminho no código do componente nem lidar com CORS no dev.
      proxy: {
        "/dados": { target: FLASK_API_URL, changeOrigin: true },
        "/horario": { target: FLASK_API_URL, changeOrigin: true },
      },
    },
  },
});
