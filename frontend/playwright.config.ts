import { defineConfig } from '@playwright/test'
import path from 'node:path'

export default defineConfig({
  testDir: './e2e', workers: 1, use: { baseURL: 'http://127.0.0.1:5174' },
  webServer: [
    { command: `${process.platform === 'win32' ? '..\\.venv\\Scripts\\python.exe' : '../.venv/bin/python'} dev_workspace.py`, cwd: '../backend', url: 'http://127.0.0.1:8001/ready', timeout: 60000,
      env: { DATABASE_URL: `sqlite:///${path.resolve('../backend/browser-test.db').replace(/\\/g, '/')}`, APP_ENV: 'test', APP_ORIGINS: 'http://127.0.0.1:5174', FILE_ENCRYPTION_KEY: Buffer.alloc(32).toString('base64url') + '=' } },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort', url: 'http://127.0.0.1:5174',
      env: { VITE_APP_MODE: 'workspace', VITE_API_BASE_URL: 'http://127.0.0.1:8001' } },
  ],
})
