import * as vscode from 'vscode';

const MODULE_DEFAULTS: Record<string, boolean> = {
    driftguard: true,
    contextlens: true,
    ghostmemory: true,
    rulesforge: false,
    taskweaver: false,
};

export function isModuleEnabled(moduleId: string): boolean {
    const config = vscode.workspace.getConfiguration('pruvagraph.modules');
    const defaultVal = MODULE_DEFAULTS[moduleId] ?? false;
    return config.get<boolean>(`${moduleId}.enabled`, defaultVal);
}

