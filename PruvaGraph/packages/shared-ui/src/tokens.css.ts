export const DESIGN_TOKENS = `
:root {
  --omni-bg: var(--vscode-editor-background, #FAFAFA);
  --omni-surface: var(--vscode-sideBar-background, #FFFFFF);
  --omni-border: var(--vscode-widget-border, #E4E4E4);
  --omni-text-primary: var(--vscode-editor-foreground, #1A1A1A);
  --omni-text-secondary: var(--vscode-descriptionForeground, #6B6B6B);
  --omni-accent: var(--vscode-button-background, #3D5AFE);
  --omni-warn: var(--vscode-editorWarning-foreground, #A32D2D);
  --omni-ok: var(--vscode-testing-iconPassed, #3B6D11);
}

@media (prefers-color-scheme: dark) {
    :root {
        --omni-bg: var(--vscode-editor-background, #1A1A1A);
        --omni-surface: var(--vscode-sideBar-background, #222222);
        --omni-border: var(--vscode-widget-border, #333333);
        --omni-text-primary: var(--vscode-editor-foreground, #EDEDED);
        --omni-text-secondary: var(--vscode-descriptionForeground, #9A9A9A);
        --omni-accent: var(--vscode-button-background, #7C8CFF);
        --omni-warn: var(--vscode-editorWarning-foreground, #F09595);
        --omni-ok: var(--vscode-testing-iconPassed, #97C459);
    }
}

body {
  background-color: var(--omni-bg);
  color: var(--omni-text-primary);
  font-family: -apple-system, "Segoe UI", Inter, sans-serif;
  margin: 0;
  padding: 16px;
}

.surface {
  background-color: var(--omni-surface);
  border: 0.5px solid var(--omni-border);
  border-radius: 4px;
}
`;
