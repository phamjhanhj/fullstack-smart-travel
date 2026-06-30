import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class AiStreamService {
  private readonly baseUrl = 'http://localhost:8000/api';

  async streamMessage(
    tripId: string,
    message: string,
    onDelta: (delta: string) => void,
    onDone: (messageId: string, suggestionId: string | null) => void,
    onError: (err: any) => void
  ): Promise<void> {
    const token = localStorage.getItem('access_token');
    try {
      const response = await fetch(`${this.baseUrl}/trips/${tripId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ message, stream: true })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
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
