import { useState, type FormEvent } from 'react';
import type { ProcessEventUseCase } from '@/application';
import { useEventUploader } from '@/presentation/hooks/useEventUploader';
import { FileDropper } from './FileDropper';
import { Spinner } from './Spinner';
import { SuccessModal } from './SuccessModal';

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
    <>
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
            placeholder="Tinder Night DD-MM 24-35"
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

        {/* ── ERROR feedback ──────────────────────────── */}
        {state.status === 'ERROR' && state.error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <svg
                className="h-5 w-5 shrink-0 text-red-400"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
              <p className="text-red-300 text-sm font-medium">
                No se pudo procesar el evento
              </p>
            </div>
            <p className="text-red-300/80 text-xs pl-7">{state.error}</p>
            <button
              type="button"
              onClick={handleReset}
              className="ml-7 text-sm text-red-400 underline hover:text-red-300 transition-colors"
            >
              Reintentar
            </button>
          </div>
        )}
      </form>

      {/* ── SUCCESS modal ───────────────────────────── */}
      {state.status === 'SUCCESS' && state.result && (
        <SuccessModal result={state.result} onClose={handleReset} />
      )}
    </>
  );
}