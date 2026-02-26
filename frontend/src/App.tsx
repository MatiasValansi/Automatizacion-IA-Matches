/**
 * App Root — Composition Root
 */

import { useMemo } from 'react';
import { createEventApiAdapter } from '@/infrastructure';
import { createProcessEventUseCase } from '@/application';
import { EventUploader } from '@/presentation';

// 1. Importamos el logo
import logo from './media/logo.png'; 

function App() {
  const useCase = useMemo(() => {
    const api = createEventApiAdapter();
    return createProcessEventUseCase(api);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-eventeando-darker to-eventeando-dark flex flex-col items-center px-4 py-12">
      
      {/* ── Header ──────────────────────────────────── */}
      <header className="mb-12 text-center flex flex-col items-center">
        
        
        <img 
          src={logo} 
          alt="Eventeando Logo" 
          className="h-32 w-auto object-contain drop-shadow-2xl" 
        />

        <p className="mt-4 text-base text-white/60 font-sans whitespace-pre-wrap">
          A p o s t a n d o   p o r   l o   r e a l 
        </p>
      </header>

      {/* ── Main card ───────────────────────────────── */}
      <main className="w-full max-w-lg rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 p-8 shadow-2xl">
        <EventUploader useCase={useCase} />
      </main>

      {/* ── Footer ──────────────────────────────────── */}
      <footer className="mt-12 text-xs text-white/30">
        © {new Date().getFullYear()} Eventeando · Powered by Juan y Matías
      </footer>
    </div>
  );
}

export default App;