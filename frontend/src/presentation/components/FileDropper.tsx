import { useCallback, useRef, useState } from 'react';

interface FileDropperProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
  disabled?: boolean;
}

export function FileDropper({ files, onFilesChange, disabled }: FileDropperProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const addFiles = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return;
      const next = [...files, ...Array.from(incoming)];
      onFilesChange(next);
    },
    [files, onFilesChange],
  );

  const removeFile = useCallback(
    (index: number) => {
      onFilesChange(files.filter((_, i) => i !== index));
    },
    [files, onFilesChange],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (!disabled) addFiles(e.dataTransfer.files);
    },
    [addFiles, disabled],
  );

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!disabled) inputRef.current?.click();
          }
        }}
        className={`
          flex flex-col items-center justify-center gap-2
          rounded-xl border-2 border-dashed p-8
          cursor-pointer transition-colors duration-200
          ${isDragging
            ? 'border-eventeando-accent bg-eventeando-accent/10'
            : 'border-white/30 hover:border-eventeando-accent/60 bg-white/5'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        {/* upload icon */}
        <svg
          className="h-10 w-10 text-eventeando-accent"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>

        <p className="text-sm text-white/70">
          Arrastrá las planillas acá o{' '}
          <span className="text-eventeando-accent font-semibold underline">
            elegí archivos
          </span>
        </p>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/*"
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
          disabled={disabled}
        />
      </div>

      {/* file list */}
      {files.length > 0 && (
        <ul className="space-y-1 max-h-40 overflow-y-auto pr-1">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between rounded-lg bg-white/10 px-3 py-2 text-sm"
            >
              <span className="truncate mr-2">{file.name}</span>
              <button
                type="button"
                onClick={() => removeFile(idx)}
                disabled={disabled}
                className="text-white/50 hover:text-red-400 transition-colors shrink-0"
                aria-label={`Eliminar ${file.name}`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
