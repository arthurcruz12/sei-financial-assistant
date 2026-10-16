import assert from 'node:assert/strict';
import {allocate,forecast,cleanPoints,csvRows} from '../lib/economics.ts';
for(const risk of ['Conservador','Moderado','Dinâmico'])for(const budget of [1,999.99,10000])for(const horizon of [1,5,40]){const rows=allocate(budget,risk,horizon);assert.equal(rows.reduce((s,r)=>s+r.weight,0),100);assert.equal(Math.round(rows.reduce((s,r)=>s+r.amount,0)*100),Math.round(budget*100));}
assert.throws(()=>allocate(-1,'Moderado',5));assert.throws(()=>allocate(100,'Outro',5));
assert.deepEqual(cleanPoints([{date:'2099-01-01',value:1},{date:'2025-01-01',value:NaN},{date:'2025-01-02',value:2}],new Date('2026-01-01')),[{date:'2025-01-02',value:2}]);
assert.deepEqual(csvRows('a,"b,c"\n1,2'),[['a','b,c'],['1','2']]);
assert.throws(()=>forecast([],12));
const f=forecast(Array.from({length:30},(_,i)=>({date:'2025-01-01',value:10+Math.sin(i)})),12);assert.equal(f.length,13);assert.equal(f[0].high,f[0].low);assert.ok(f[12].high-f[12].low>f[1].high-f[1].low);
console.log('PASS: allocation conservation, validation, future/nonfinite filtering, CSV, forecast uncertainty.');
