export interface IEmbedder {
    embed(text: string): Promise<Float32Array | null>;
    similarity(a: Float32Array, b: Float32Array): number;
}

export class NoOpEmbedder implements IEmbedder {
    async embed(_text: string): Promise<Float32Array | null> {
        return null;
    }
    similarity(_a: Float32Array, _b: Float32Array): number {
        return 0;
    }
}
