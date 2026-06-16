module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [
      2,
      'always',
      [
        'cli',
        'pipeline',
        'mcp',
        'compress',
        'cache',
        'router',
        'detect',
        'export',
        'ui',
        'docs',
        'core',
        'deps',
        'tests'
      ]
    ],
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'docs',
        'style',
        'refactor',
        'perf',
        'test',
        'build',
        'ci',
        'chore',
        'revert'
      ]
    ],
    'subject-case': [2, 'always', 'lower-case']
  }
};
