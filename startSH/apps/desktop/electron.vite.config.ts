import { resolve } from 'node:path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'

const sharedRoot = resolve(__dirname, '../../packages/shared/src/index.ts')

export default defineConfig({
  main: {
    resolve: {
      alias: { '@linux-dev-home/shared': sharedRoot },
    },
    plugins: [externalizeDepsPlugin()],
  },
  preload: {
    resolve: {
      alias: { '@linux-dev-home/shared': sharedRoot },
    },
    plugins: [externalizeDepsPlugin()],
  },
  renderer: {
    resolve: {
      alias: {
        '@linux-dev-home/shared': sharedRoot,
      },
    },
    plugins: [react()],
  },
})
