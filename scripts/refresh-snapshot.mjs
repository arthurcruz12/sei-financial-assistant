import {mkdir,writeFile} from 'node:fs/promises';
const since=new Date(Date.now()-400*86400000).toISOString().slice(0,10);
const data={};
for(const [id,code] of [['fedfunds','DFF'],['liquidity','WALCL'],['stress','STLFSI4']]){
 const r=await fetch(`https://fred.stlouisfed.org/graph/fredgraph.csv?id=${code}&cosd=${since}`,{signal:AbortSignal.timeout(25000)});
 if(!r.ok)throw Error(`FRED ${r.status}`);
 const rows=(await r.text()).trim().split(/\r?\n/).slice(1).map(s=>s.split(','));
 const points=rows.filter(r=>/^\d{4}-\d{2}-\d{2}$/.test(r[0])&&r[1]!=='.'&&r[1]!==''&&Number.isFinite(Number(r[1]))&&r[0]<=new Date().toISOString().slice(0,10)).map(([date,value])=>({date,value:Number(value)}));
 if(!points.length)throw Error('No valid data');
 data[id]={points,fetchedAt:new Date().toISOString(),downloadUrl:`https://fred.stlouisfed.org/graph/fredgraph.csv?id=${code}&cosd=${since}`};
 console.log(id,points.length,points.at(-1));
}
await mkdir('lib',{recursive:true});await writeFile('lib/snapshot.json',JSON.stringify(data));
