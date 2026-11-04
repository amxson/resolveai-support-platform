import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import Workspace from './Workspace'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {import.meta.env.VITE_APP_MODE === 'workspace' ? <Workspace /> : <App />}
  </React.StrictMode>,
)

