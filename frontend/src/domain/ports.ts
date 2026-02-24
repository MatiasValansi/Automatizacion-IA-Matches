/**
 * Domain Ports (Interfaces)
 *
 * Contracts that the Application layer depends on.
 * Infrastructure adapters implement these interfaces,
 * achieving Dependency Inversion (SOLID "D").
 */

import type { ProcessEventResult } from './entities';

/** Port for the event-processing API */
export interface EventApiPort {
  /**
   * Sends event data (name + spreadsheet images) to the backend.
   * @param eventName  – human-readable event identifier
   * @param files      – binary image files (screenshots of spreadsheets)
   * @returns the processing result with detected matches
   * @throws ApiError on transport or server failures
   */
  processEvent(eventName: string, files: File[]): Promise<ProcessEventResult>;
}

/** Standardised error that adapters should throw */
export class ApiError extends Error {
  readonly statusCode: number | null;
  readonly detail?: string;

  constructor(
    message: string,
    statusCode: number | null = null,
    detail?: string,
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}
