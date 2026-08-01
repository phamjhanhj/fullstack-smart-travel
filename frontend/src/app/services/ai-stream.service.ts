import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '../config/api.config';

@Injectable({
  providedIn: 'root',
})
export class AiStreamService {
  private readonly baseUrl = inject(API_BASE_URL);

  async streamMessage(
    tripId: string,
    message: string,
    onDelta: (delta: string) => void,
    onDone: (messageId: string, suggestionId: string | null) => void,
    onError: (err: any) => void
  ): Promise<void> {
    const token = sessionStorage.getItem('access_token');
    try {
      const response = await fetch(`${this.baseUrl}/trips/${tripId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({ message, stream: true })
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw { status: response.status, error: errorBody };
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Save the last partial line back to the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            try {
              const parsed = JSON.parse(jsonStr);
              if (parsed.data) {
                if (parsed.data.delta) {
                  onDelta(parsed.data.delta);
                }
                if (parsed.data.done) {
                  onDone(parsed.data.message_id, parsed.data.suggestion_id);
                }
              }
            } catch (e) {
              console.warn('Could not parse SSE JSON line:', trimmed, e);
            }
          }
        }
      }
    } catch (err) {
      onError(err);
    }
  }
}
