import { IEventBus, PRUVALEXEventMap } from '@pruvalex/shared-types';

export class EventBus implements IEventBus<PRUVALEXEventMap> {
    private listeners: { [K in keyof PRUVALEXEventMap]?: Array<(payload: PRUVALEXEventMap[K]) => void> } = {};

    emit<K extends keyof PRUVALEXEventMap>(event: K, payload: PRUVALEXEventMap[K]): void {
        const eventListeners = this.listeners[event];
        if (eventListeners) {
            for (const listener of eventListeners) {
                try {
                    listener(payload);
                } catch (error) {
                    console.error(`Error in EventBus listener for ${event}:`, error);
                }
            }
        }
    }

    on<K extends keyof PRUVALEXEventMap>(event: K, listener: (payload: PRUVALEXEventMap[K]) => void): { dispose: () => void } {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event]!.push(listener);

        return {
            dispose: () => {
                const arr = this.listeners[event];
                if (arr) {
                    const idx = arr.indexOf(listener);
                    if (idx !== -1) {
                        arr.splice(idx, 1);
                    }
                }
            }
        };
    }
}

