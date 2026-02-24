import { useEffect, useRef } from 'react';
import type { ProcessEventResult } from '@/domain/entities';

interface SuccessModalProps {
  result: ProcessEventResult;
  onClose: () => void;
}

export function SuccessModal({ result, onClose }: SuccessModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) {
      dialog.showModal();
    }
  }, []);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="
        fixed inset-0 z-50 m-auto
        w-[90vw] max-w-md rounded-2xl border border-white/10
        bg-eventeando-darker p-0 text-white
        shadow-2xl shadow-black/50
        backdrop:bg-black/60 backdrop:backdrop-blur-sm
      "
    >
      <div className="flex flex-col items-center gap-5 p-8">
        {/* ── Check icon ───────────────────────────── */}
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20">
          <svg
            className="h-9 w-9 text-green-400"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4.5 12.75l6 6 9-13.5"
            />
          </svg>
        </div>

        {/* ── Title ────────────────────────────────── */}
        <h2 className="font-serif text-2xl font-bold text-center">
          ¡Evento procesado!
        </h2>

        {/* ── Stats ────────────────────────────────── */}
        <div className="w-full space-y-2 rounded-xl bg-white/5 p-4 text-sm">
          <div className="flex justify-between">
            <span className="text-white/60">Evento</span>
            <span className="font-medium">{result.event_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/60">Imágenes procesadas</span>
            <span className="font-medium">{result.processed_images}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/60">Matches encontrados</span>
            <span className="font-bold text-eventeando-accent">
              {result.match_count}
            </span>
          </div>
        </div>

        {/* ── Google Sheets link ────────────────────── */}
        {result.sheet_url && (
          <a
            href={result.sheet_url}
            target="_blank"
            rel="noopener noreferrer"
            className="
              flex w-full items-center justify-center gap-2
              rounded-xl bg-green-600 px-6 py-3
              font-semibold text-white text-base
              shadow-lg shadow-green-600/30
              transition-all duration-200
              hover:bg-green-500 hover:shadow-green-500/40
              active:scale-[0.98]
            "
          >
            {/* Google Sheets icon */}
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 11V9h-5V5h-2v4H7v2h5v4h2v-4h5z" opacity="0" />
              <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11z" />
              <path d="M8 15h8v2H8zm0-4h8v2H8z" />
            </svg>
            Abrir Google Sheets
          </a>
        )}

        {/* ── Close ────────────────────────────────── */}
        <button
          type="button"
          onClick={onClose}
          className="
            w-full rounded-xl border border-white/20 bg-white/5
            px-6 py-3 text-sm font-medium text-white/70
            transition-all hover:bg-white/10 hover:text-white
          "
        >
          Procesar otro evento
        </button>
      </div>
    </dialog>
  );
}
