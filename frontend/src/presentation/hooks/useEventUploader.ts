/**
 * Presentation Hook — useEventUploader
 *
 * Encapsulates all state logic for the upload flow.
 * The component stays as a pure UI renderer.
 */

import { useCallback, useReducer } from 'react';
import type { UploadState } from '@/domain/entities';
import { INITIAL_UPLOAD_STATE } from '@/domain/entities';
import type { ProcessEventUseCase } from '@/application';

// ── Actions ────────────────────────────────────────────────

type Action =
  | { type: 'SUBMIT' }
  | { type: 'SUCCESS'; payload: UploadState['result'] }
  | { type: 'ERROR'; payload: string }
  | { type: 'RESET' };

function reducer(_state: UploadState, action: Action): UploadState {
  switch (action.type) {
    case 'SUBMIT':
      return { status: 'LOADING', result: null, error: null };
    case 'SUCCESS':
      return { status: 'SUCCESS', result: action.payload, error: null };
    case 'ERROR':
      return { status: 'ERROR', result: null, error: action.payload };
    case 'RESET':
      return INITIAL_UPLOAD_STATE;
  }
}

// ── Hook ───────────────────────────────────────────────────

export function useEventUploader(useCase: ProcessEventUseCase) {
  const [state, dispatch] = useReducer(reducer, INITIAL_UPLOAD_STATE);

  const submit = useCallback(
    async (eventName: string, files: File[]) => {
      dispatch({ type: 'SUBMIT' });
      try {
        const result = await useCase.execute({ eventName, files });
        dispatch({ type: 'SUCCESS', payload: result });
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'Error desconocido.';
        dispatch({ type: 'ERROR', payload: message });
      }
    },
    [useCase],
  );

  const reset = useCallback(() => dispatch({ type: 'RESET' }), []);

  return { state, submit, reset } as const;
}
