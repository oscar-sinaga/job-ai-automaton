const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'oscar-shortcut-test-'));
try {
  const env = path.join(temporary, 'test.env');
  const output = path.join(temporary, 'capture.oscar-shortcut.zip');
  fs.writeFileSync(env, 'OSCAR_API_KEY=simulation-only-shortcut-test\n', { mode: 0o600 });
  execFileSync('python3', ['scripts/mobile/create_android_shortcut.py', '--env-file', env,
    '--api-base-url', 'http://127.0.0.1:8000/api/v1', '--output', output]);
  const document = JSON.parse(execFileSync('python3', ['-c',
    'import sys,zipfile;print(zipfile.ZipFile(sys.argv[1]).read("shortcuts.json").decode())', output], { encoding: 'utf8' }));
  assert.equal(fs.statSync(output).mode & 0o777, 0o600);
  const shortcut = document.categories[0].shortcuts[0];
  assert.equal(shortcut.url, 'http://127.0.0.1:8000/api/v1/jobs/capture');
  assert.doesNotThrow(() => JSON.parse(shortcut.bodyContent), 'Unresolved template must pass native preflight');
  const values = new Map(document.variables.map(variable => [variable.id, variable.value]));
  const byName = key => document.variables.find(variable => variable.key === `oscar_${key}`).id;
  // Match the app's v4.9 raw-placeholder grammar, including its UUIDv4-only
  // branch. Import/JS UUID validation is broader and must not mask this case.
  const rawPlaceholder = /\{\{([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|[0-9]+|[A-Za-z0-9_]{1,30})\}\}/gi;
  const resolve = template => template.replace(rawPlaceholder, (_, key) => {
    const variable = document.variables.find(variable => variable.id === key || variable.key === key);
    assert(variable, `Unknown variable: ${key}`);
    return values.get(variable.id);
  });
  const run = (text, title) => {
    values.set(byName('shared_text'), text);
    values.set(byName('shared_title'), title);
    vm.runInNewContext(shortcut.codeOnPrepare, {
      getVariable: id => values.get(id), setVariable: (id, value) => values.set(id, value)
    });
    const body = resolve(shortcut.bodyContent);
    assert(!body.includes('{{'), 'All request placeholders must resolve in the native app');
    const headers = Object.fromEntries(shortcut.headers.map(header => [header.key, resolve(header.value)]));
    assert.equal(headers['X-API-Key'], 'simulation-only-shortcut-test');
    assert.equal(headers['Idempotency-Key'], values.get(byName('capture_key')));
    return { body: JSON.parse(body), key: values.get(byName('capture_key')) };
  };
  const text = 'Data Engineer "Python"\nhttps://example.com/jobs/1?track=android';
  const first = run(text, 'Data Engineer');
  assert.equal(first.body.url, 'https://example.com/jobs/1?track=android');
  assert.equal(first.body.shared_text, text);
  assert.equal(first.body.page_title, 'Data Engineer');
  assert.equal(first.body.capture_method, 'mobile_share');
  assert.match(first.key, /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
  assert.equal(run(text, 'Data Engineer').key, first.key, 'Retry must retain the same idempotency key');
  assert.notEqual(run('https://example.com/jobs/2', '').key, first.key);
  assert.equal(run('https://example.com/jobs/3', 'https://example.com/jobs/3').body.page_title, '');
  assert.throws(() => run('no link', ''), /No URL found/);
  assert.throws(() => execFileSync('python3', ['scripts/mobile/create_android_shortcut.py', '--env-file', env,
    '--api-base-url', 'http://192.168.1.2:8000/api/v1', '--output', path.join(temporary, 'unsafe.zip')], { stdio: 'pipe' }));
  assert.equal(document.variables.find(variable => variable.key === 'oscar_api_key').isSecret, true);
  assert(document.variables.every(variable => variable.isExcludeValueFromExport));
  console.log('PASS Android shortcut payload, quoting, retries, private file and HTTPS checks');
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
