import { DESIGN_TOKENS } from './tokens.css.js';

export function getWebviewShell(title: string, bodyHtml: string): string {
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <style>
        ${DESIGN_TOKENS}
    </style>
</head>
<body>
    ${bodyHtml}
</body>
</html>
    `.trim();
}
