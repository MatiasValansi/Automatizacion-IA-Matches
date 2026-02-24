/**
 * App Root — Composition Root
 *
 * This is the ONLY place where we wire infrastructure → application → presentation.
 * All dependencies flow inward (Hexagonal Architecture).
 */

import { useMemo } from 'react';
import { createEventApiAdapter } from '@/infrastructure';
import { createProcessEventUseCase } from '@/application';
import { EventUploader } from '@/presentation';

function App() {
  const useCase = useMemo(() => {
    const api = createEventApiAdapter();
    return createProcessEventUseCase(api);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-eventeando-darker to-eventeando-dark flex flex-col items-center px-4 py-12">
      {/* ── Header ──────────────────────────────────── */}
      <header className="mb-12 text-center">
        <h1 className="font-serif text-5xl font-black tracking-tight text-white drop-shadow-lg">
          Eventeando
        </h1>
        <p className="mt-2 text-base text-white/60 font-sans">
          AI Social Matcher — Encontrá tus matches en segundos
        </p>
      </header>

      {/* ── Main card ───────────────────────────────── */}
      <main className="w-full max-w-lg rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 p-8 shadow-2xl">
        <EventUploader useCase={useCase} />
      </main>

      {/* ── Footer ──────────────────────────────────── */}
      <footer className="mt-12 text-xs text-white/30">
        © {new Date().getFullYear()} Eventeando · Powered by AI
      </footer>
    </div>
  );
}

export default App;
