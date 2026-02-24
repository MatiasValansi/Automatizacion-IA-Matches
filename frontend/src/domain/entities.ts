/**
 * Domain Entities — AI Social Matcher (Eventeando)
 *
 * Pure data structures that model the core business concepts.
 * No framework imports, no side-effects.
 */

export interface Participant {
  readonly name: string;
  readonly phone: string;
}

export interface Match {
  readonly person_a: Participant; // Cambiado de personA a person_a
  readonly person_b: Participant; // Cambiado de personB a person_b
}

export interface ProcessEventResult {
  readonly event_name: string;
  readonly processed_images: number;
  readonly match_count: number;
  readonly sheet_url: string | null;
  readonly status: string;
}

/** Upload status finite state machine */
export type UploadStatus = 'IDLE' | 'LOADING' | 'SUCCESS' | 'ERROR';

export interface UploadState {
  readonly status: UploadStatus;
  readonly result: ProcessEventResult | null;
  readonly error: string | null;
}

export const INITIAL_UPLOAD_STATE: UploadState = {
  status: 'IDLE',
  result: null,
  error: null,
};
