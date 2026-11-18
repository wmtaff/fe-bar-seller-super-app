import { createBrowserRouter, RouterProvider, NavLink, Outlet } from 'react-router';
import { useCallback, useEffect, useState } from 'react';
import { Badge, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@databricks/appkit-ui/react';
import { api } from './lib/api';
import { PersonaContext, type Me } from './lib/persona';
import { MyWeekPage } from './pages/MyWeekPage';
import { DealPage } from './pages/DealPage';
import { AskGeniePage } from './pages/AskGeniePage';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

function PersonaSwitcher({ me, onSwitch, busy }: { me: Me | null; onSwitch: (p: string) => void; busy: boolean }) {
  // Seller / Manager only. `empty` is a hidden test persona reachable through PUT /api/persona.
  const value = me?.persona_key === 'manager' ? 'manager' : me?.persona_key === 'seller' ? 'seller' : undefined;
  return (
    <Select value={value} onValueChange={onSwitch} disabled={busy || !me}>
      <SelectTrigger className="w-[220px]" aria-label="Persona">
        <SelectValue placeholder={me ? me.persona_name : 'Loading persona…'} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="seller">Seller: Jordan Rivera</SelectItem>
        <SelectItem value="manager">Manager: Morgan Lee</SelectItem>
      </SelectContent>
    </Select>
  );
}

function Layout() {
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);

  const loadMe = useCallback(() => {
    api<Me>('/api/me')
      .then((m) => {
        setMe(m);
        setMeError(null);
      })
      .catch((e: Error) => setMeError(e.message));
  }, []);
  useEffect(loadMe, [loadMe]);

  const onSwitch = async (persona: string) => {
    setBusy(true);
    try {
      await api('/api/persona', { method: 'PUT', body: { persona } });
      loadMe();
      setVersion((v) => v + 1);
    } catch (e) {
      setMeError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <PersonaContext.Provider value={{ me, version }}>
      <div className="min-h-screen bg-background flex flex-col">
        <header className="border-b px-4 md:px-6 py-3 flex flex-wrap items-center gap-4">
          <h1 className="text-lg font-semibold text-foreground">Fleetwise Seller Hub</h1>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navLinkClass}>My Week</NavLink>
            <NavLink to="/genie" className={navLinkClass}>Ask Genie</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {meError && <span className="text-xs text-destructive">Persona: {meError}</span>}
            {me && <Badge variant="secondary" title="Signed-in workspace user">{me.email}</Badge>}
            {me && <Badge variant="outline">{me.role}</Badge>}
            <PersonaSwitcher me={me} onSwitch={(p) => void onSwitch(p)} busy={busy} />
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </PersonaContext.Provider>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <MyWeekPage /> },
      { path: '/deals/:id', element: <DealPage /> },
      { path: '/genie', element: <AskGeniePage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
