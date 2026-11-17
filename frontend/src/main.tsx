import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App, ROUTER_FUTURE } from './App';
import { ApiProvider } from './api/ApiProvider';
import { createApiFromEnv } from './api';
import { SessionProvider } from './session/SessionProvider';
import './styles/tokens.css';
import './styles/global.css';
import './styles/components.css';

const api = createApiFromEnv();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ApiProvider api={api}>
      <SessionProvider>
        <BrowserRouter future={ROUTER_FUTURE}>
          <App />
        </BrowserRouter>
      </SessionProvider>
    </ApiProvider>
  </StrictMode>,
);
