import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Kept separate from vite.config.ts so the TanStack Start (SSR) plugin does not
// run during tests. Path aliases (`@/…`) come from tsconfig.json.
export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
    coverage: {
      provider: "v8",
      // Only source files: a bare "src/routes/**" would also match README.md and
      // the provider would try (and fail) to parse it as JavaScript.
      include: ["src/{lib,routes,features,hooks}/**/*.{ts,tsx}"],
      exclude: ["src/routeTree.gen.ts", "src/**/*.test.{ts,tsx}"],
    },
  },
});
