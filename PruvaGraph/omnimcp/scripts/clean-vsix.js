const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const files = fs.readdirSync(rootDir);

files.forEach(file => {
    if (file.endsWith('.vsix')) {
        console.log(`Deleting old VSIX: ${file}`);
        fs.unlinkSync(path.join(rootDir, file));
    }
});
console.log('Cleaned old .vsix files.');
