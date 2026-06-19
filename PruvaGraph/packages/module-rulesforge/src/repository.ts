import { IGraphStore, ModuleRepository } from '@pruvalex/shared-types';

export interface IRule {
    id: string;
    rule_name: string;
    layer: string;
    condition: string;
    action: string;
    source: string;
    is_active: number;
    created_at: number;
    updated_at: number;
}

export class RulesForgeRepository {
    private repo: ModuleRepository;

    constructor(store: IGraphStore) {
        this.repo = store.scope('rulesforge');
    }

    insertRule(id: string, rule_name: string, condition: string, action: string, layer: string = 'global', source: string = 'user') {
        this.repo.run(`
            INSERT INTO rulesforge_rules (id, rule_name, layer, condition, action, source, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        `, id, rule_name, layer, condition, action, source, Date.now(), Date.now());
    }

    getRules(layer?: string): IRule[] {
        if (layer) {
            return this.repo.all<IRule>(
                `SELECT * FROM rulesforge_rules WHERE is_active = 1 AND layer = ? ORDER BY updated_at ASC`,
                layer
            );
        }
        return this.repo.all<IRule>(`SELECT * FROM rulesforge_rules WHERE is_active = 1 ORDER BY updated_at ASC`);
    }

    deleteRule(id: string) {
        this.repo.run(`DELETE FROM rulesforge_rules WHERE id = ?`, id);
    }
}

