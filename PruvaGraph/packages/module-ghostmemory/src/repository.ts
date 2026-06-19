import { IGraphStore, ModuleRepository } from '@pruvalex/shared-types';

export interface IGhostMemoryEntry {
    id: string;
    content: string;
    tags: string;
    project: string;
    embedding: Buffer;
    created_at: number;
}

export class GhostMemoryRepository {
    private repo: ModuleRepository;

    constructor(store: IGraphStore) {
        this.repo = store.scope('ghostmemory');
    }

    insertMemory(id: string, content: string, tags: string[], project: string, embedding?: Float32Array | null) {
        this.repo.run(
            `INSERT INTO ghostmemory_entries (id, content, tags, project, embedding, created_at)
             VALUES (?, ?, ?, ?, ?, ?)`,
            id, content, JSON.stringify(tags), project,
            embedding ? Buffer.from(embedding.buffer) : null,
            Date.now()
        );
    }

    recallRelevant(query: string, project: string, topK = 5): IGhostMemoryEntry[] {
        return this.repo.all<IGhostMemoryEntry>(
            `SELECT * FROM ghostmemory_entries
             WHERE project = ? AND (content LIKE ? OR tags LIKE ?)
             ORDER BY created_at DESC LIMIT ?`,
            project, `%${query}%`, `%${query}%`, topK
        );
    }

    updateTags(id: string, tags: string[]) {
        this.repo.run(
            `UPDATE ghostmemory_entries SET tags = ? WHERE id = ?`,
            JSON.stringify(tags),
            id
        );
    }
}

