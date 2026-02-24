import { useState, type FormEvent } from 'react';
import type { ProcessEventUseCase } from '@/application';
import { useEventUploader } from '@/presentation/hooks/useEventUploader';
import { FileDropper } from './FileDropper';
import { Spinner } from './Spinner';

interface EventUploaderProps {
  useCase: ProcessEventUseCase;
}

export function EventUploader({ useCase }: EventUploaderProps) {
  const { state, submit, reset } = useEventUploader(useCase);
  const [eventName, setEventName] = useState('');
  const [files, setFiles] = useState<File[]>([]);

  const isLoading = state.status === 'LOADING';

  const canSubmit =
    eventName.trim().length > 0 && files.length > 0 && !isLoading;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    void submit(eventName, files);
  };

  const handleReset = () => {
    reset();
    setEventName('');
    setFiles([]);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-lg mx-auto space-y-6"
    >
      {/* ── Event name ──────────────────────────────── */}
      <div className="space-y-2">
        <label
          htmlFor="eventName"
          className="block text-sm font-medium text-white/80"
        >
          Nombre del evento
        </label>
        <input
          id="eventName"
          type="text"
          placeholder="Networking Tech 2026"
          value={eventName}
          onChange={(e) => setEventName(e.target.value)}
          disabled={isLoading}
          className="
            w-full rounded-xl border border-white/20 bg-white/10
            px-4 py-3 text-white placeholder-white/40
            outline-none transition-all
            focus:border-eventeando-accent focus:ring-2 focus:ring-eventeando-accent/40
            disabled:opacity-50
          "
        />
      </div>

      {/* ── File dropper ────────────────────────────── */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-white/80">
          Planillas (imágenes)
        </label>
        <FileDropper
          files={files}
          onFilesChange={setFiles}
          disabled={isLoading}
        />
      </div>

      {/* ── Submit button ───────────────────────────── */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="
          flex w-full items-center justify-center gap-2
          rounded-xl bg-eventeando-purple px-6 py-3
          font-semibold text-white text-base
          shadow-lg shadow-eventeando-purple/30
          transition-all duration-200
          hover:bg-eventeando-accent hover:shadow-eventeando-accent/40
          active:scale-[0.98]
          disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-eventeando-purple
        "
      >
        {isLoading ? (
          <>
            <Spinner /> Procesando…
          </>
        ) : (
          'Procesar Evento'
        )}
      </button>

      {/* ── SUCCESS feedback ────────────────────────── */}
      {state.status === 'SUCCESS' && state.result && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-center space-y-2">
          <p className="text-green-300 font-semibold text-lg">
            ¡Listo! Se encontraron{' '}
            <span className="text-white font-bold">
              {state.result.matchCount}
            </span>{' '}
            matches.
          </p>
          <button
            type="button"
            onClick={handleReset}
            className="text-sm text-green-400 underline hover:text-green-300 transition-colors"
          >
            Procesar otro evento
          </button>
        </div>
      )}

      {/* ── ERROR feedback ──────────────────────────── */}
      {state.status === 'ERROR' && state.error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-center space-y-2">
          <p className="text-red-300 text-sm">{state.error}</p>
          <button
            type="button"
            onClick={handleReset}
            className="text-sm text-red-400 underline hover:text-red-300 transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}
    </form>
  );
}
