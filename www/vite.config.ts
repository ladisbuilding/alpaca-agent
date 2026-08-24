import { defineConfig } from 'vite'
import tsConfigPaths from 'vite-tsconfig-paths'
import { cloudflare } from '@cloudflare/vite-plugin'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  server: { port: 3031, host: true },
  plugins: [
    tsConfigPaths({ projects: ['./tsconfig.json'] }),
    cloudflare({
      viteEnvironment: { name: 'ssr' },
      configPath: './wrangler.jsonc',
      persistState: true,
      inspectorPort: false,
    }),
    tanstackStart(),
    viteReact(),
    tailwindcss(),
  ],
})
