import { useEffect, useRef, useState } from 'react';
import type { ProcessEventResult } from '@/domain/entities';

interface SuccessModalProps {
  result: ProcessEventResult;
  onClose: () => void;
}

export function SuccessModal({ result, onClose }: SuccessModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) {
      dialog.showModal();
    }
  }, []);

  const copyUrl = () => {
    if (!result.sheet_url) return;
    navigator.clipboard.writeText(result.sheet_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

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
        {result.sheet_url ? (
          <div className="w-full space-y-2">
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
              <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm4 18H6V4h7v5h5v11z" />
                <path d="M8 15h8v2H8zm0-4h8v2H8z" />
              </svg>
              Abrir Google Sheets
            </a>

            {/* URL copiable */}
            <div className="flex items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-2">
              <span className="flex-1 truncate text-xs text-white/50 font-mono">
                {result.sheet_url}
              </span>
              <button
                type="button"
                onClick={copyUrl}
                title="Copiar enlace"
                className="shrink-0 text-white/40 hover:text-white transition-colors"
              >
                {copied ? (
                  <svg className="h-4 w-4 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="w-full flex items-start gap-3 rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-sm">
            <svg className="h-5 w-5 shrink-0 text-yellow-400 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15.75h.007v.008H12v-.008z" />
            </svg>
            <p className="text-yellow-300/90">
              Los datos se guardaron en Sheets, pero no se pudo recuperar el enlace. Buscá la hoja con el nombre <span className="font-semibold">{result.event_name}</span> en tu Google Drive.
            </p>
          </div>
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
