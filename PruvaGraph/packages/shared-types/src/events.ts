export type PRUVALEXEventMap = {
  'suggestion:accepted': { uri: string; diff: string };
  'checkpoint:created': { taskId: string; files: string[] };
  'mcp:call': { 
      server: string; 
      tool: string; 
      module: string;
      tokensIn: number; 
      tokensOut: number; 
      latencyMs: number 
  };
  'drift:detected': { uri: string; symbol: string; reason: string };
};

export interface IEventBus<T> {
  emit<K extends keyof T>(event: K, payload: T[K]): void;
  on<K extends keyof T>(event: K, listener: (payload: T[K]) => void): { dispose: () => void };
}
