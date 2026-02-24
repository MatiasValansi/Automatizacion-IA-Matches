/**
 * Application Layer — Process Event Use Case
 *
 * Orchestrates validation + API call.
 * Depends ONLY on the EventApiPort interface (Dependency Inversion).
 */

import type { EventApiPort } from '@/domain/ports';
import { ApiError } from '@/domain/ports';
import type { ProcessEventResult } from '@/domain/entities';

export interface ProcessEventInput {
  eventName: string;
  files: File[];
}

export interface ValidationError {
  field: 'eventName' | 'files';
  message: string;
}

function validate(input: ProcessEventInput): ValidationError[] {
  const errors: ValidationError[] = [];

  if (!input.eventName.trim()) {
    errors.push({
      field: 'eventName',
      message: 'El nombre del evento es obligatorio.',
    });
  }

  if (input.files.length === 0) {
    errors.push({
      field: 'files',
      message: 'Debes subir al menos una planilla.',
    });
  }

  return errors;
}

export function createProcessEventUseCase(api: EventApiPort) {
  return {
    validate,

    async execute(input: ProcessEventInput): Promise<ProcessEventResult> {
      const errors = validate(input);
      if (errors.length > 0) {
        throw new ApiError(
          errors.map((e) => e.message).join(' '),
          422,
        );
      }

      return api.processEvent(input.eventName.trim(), input.files);
    },
  };
}

export type ProcessEventUseCase = ReturnType<typeof createProcessEventUseCase>;
