import { spawnSync } from 'node:child_process'

const result = spawnSync(process.execPath, ['node_modules/typescript/bin/tsc', '-b'], { stdio: 'inherit' })
if (result.status !== 0) process.exit(result.status || 1)
const build = spawnSync(process.execPath, ['node_modules/vite/bin/vite.js', 'build'], {
  stdio: 'inherit', env: { ...process.env, VITE_APP_MODE: 'workspace', VITE_API_BASE_URL: '/api' },
})
process.exit(build.status || 0)
