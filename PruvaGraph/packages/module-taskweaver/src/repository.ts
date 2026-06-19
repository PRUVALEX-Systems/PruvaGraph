import { IGraphStore, ModuleRepository } from '@pruvalex/shared-types';

export interface ITaskCheckpoint {
    id: string;
    task_id: string;
    commit_sha: string;
    files_changed: string;
    git_sha: string;
    created_at: number;
}

export class TaskWeaverRepository {
    private repo: ModuleRepository;

    constructor(store: IGraphStore) {
        this.repo = store.scope('taskweaver');
    }

    insertCheckpoint(id: string, task_id: string, files_changed: string[], commit_sha: string, git_sha: string) {
        this.repo.run(`
            INSERT INTO taskweaver_checkpoints (id, task_id, commit_sha, files_changed, git_sha, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        `, id, task_id, commit_sha, JSON.stringify(files_changed), git_sha, Date.now());
    }

    getCheckpoints(task_id: string): ITaskCheckpoint[] {
        return this.repo.all<ITaskCheckpoint>(`SELECT * FROM taskweaver_checkpoints WHERE task_id = ? ORDER BY created_at DESC`, task_id);
    }

    getCheckpointById(id: string): ITaskCheckpoint | undefined {
        return this.repo.get<ITaskCheckpoint>(
            `SELECT * FROM taskweaver_checkpoints WHERE id = ?`, id
        );
    }
}

