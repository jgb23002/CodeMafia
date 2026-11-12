import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { ApiProvider } from './api/ApiProvider';
import { createApiFromEnv } from './api';
import { SessionProvider } from './session/SessionProvider';
import './styles/global.css';

const api = createApiFromEnv();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ApiProvider api={api}>
      <SessionProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </SessionProvider>
    </ApiProvider>
  </StrictMode>,
);
