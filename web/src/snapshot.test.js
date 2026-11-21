import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
for(const name of ['single','portfolio']) test(`${name} snapshot includes historical data`,()=>{
  const rows=readFileSync(new URL(`../public/data/${name}.csv`,import.meta.url),'utf8').trim().split('\n');
  assert.ok(rows.length>1000);
  assert.ok(rows[0].includes('ndx'));
  const manifest=JSON.parse(readFileSync(new URL(`../public/data/${name}-manifest.json`,import.meta.url),'utf8'));
  assert.equal(manifest.kind,'REAL_VENDOR_HISTORY');
});
test('exchange calendar is built',()=>assert.ok(existsSync(new URL('../public/data/xnys.json',import.meta.url))));
