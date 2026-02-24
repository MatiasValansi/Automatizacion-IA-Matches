/**
 * Infrastructure Adapter — HTTP implementation of EventApiPort
 *
 * This is the only place in the codebase that knows about Axios.
 * Swap this file to switch HTTP libraries without touching domain or application code.
 */

import axios, { type AxiosInstance, AxiosError } from 'axios';
import type { EventApiPort } from '@/domain/ports';
import { ApiError } from '@/domain/ports';
import type { ProcessEventResult } from '@/domain/entities';

const DEFAULT_BASE_URL = 'http://localhost:8000';

export function createEventApiAdapter(
  baseURL: string = DEFAULT_BASE_URL,
): EventApiPort {
  const client: AxiosInstance = axios.create({
    baseURL,
    timeout: 120_000, // 2 min — OCR + AI can be slow
  });

  return {
    async processEvent(
      eventName: string,
      files: File[],
    ): Promise<ProcessEventResult> {
      const formData = new FormData();
      formData.append('event_name', eventName);

      for (const file of files) {
        formData.append('files', file);
      }

      try {
        const { data } = await client.post<ProcessEventResult>(
          '/process-event',
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
          },
        );
        return data;
      } catch (err) {
        if (err instanceof AxiosError) {
          const status = err.response?.status ?? null;
          const detail =
            (err.response?.data as { detail?: string })?.detail ??
            err.message;

          throw new ApiError(
            `Error ${status ?? 'de red'}: ${detail}`,
            status,
            detail,
          );
        }
        throw new ApiError('Error inesperado al procesar el evento.');
      }
    },
  };
}
