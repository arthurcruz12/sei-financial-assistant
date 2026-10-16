import snapshot from './snapshot.json';
export type Point = {date:string; value:number};
export type Series = {id:string; name:string; region:string; unit:string; source:string; url:string; points:Point[]; status:string; error?:string; fetchedAt:string};
export const catalog = [
 {id:'selic',name:'Taxa Selic',region:'Brasil',unit:'% a.a.',source:'Banco Central do Brasil',url:'https://www.bcb.gov.br/controleinflacao/taxaselic',code:'432',maxAge:7},
 {id:'ipca',name:'Inflação IPCA',region:'Brasil',unit:'% mensal',source:'BCB / IBGE',url:'https://www.bcb.gov.br/estatisticas/indecoreestruturacao',code:'433',maxAge:65},
 {id:'eurusd',name:'Euro / Dólar',region:'Europa',unit:'USD por EUR',source:'Banco Central Europeu',url:'https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A',code:'',maxAge:7},
 {id:'fedfunds',name:'Fed funds efetiva',region:'EUA',unit:'% a.a.',source:'Federal Reserve / FRED',url:'https://fred.stlouisfed.org/series/DFF',code:'DFF',maxAge:7},
 {id:'liquidity',name:'Ativos do Federal Reserve',region:'EUA',unit:'milhões USD',source:'Federal Reserve / FRED',url:'https://fred.stlouisfed.org/series/WALCL',code:'WALCL',maxAge:16},
 {id:'stress',name:'Stress financeiro STLFSI4',region:'EUA',unit:'desvios-padrão',source:'Federal Reserve Bank of St. Louis',url:'https://fred.stlouisfed.org/series/STLFSI4',code:'STLFSI4',maxAge:16},
] as const;
export function csvRows(text:string):string[][] {return text.trim().split(/\r?\n/).map(line=>{const result:string[]=[];let value='',quoted=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'){if(quoted&&line[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){result.push(value);value='';}else value+=c;}result.push(value);return result;});}
export function cleanPoints(points:Point[],now=new Date()):Point[]{return points.filter(p=>/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&Number.isFinite(p.value)&&p.date<=now.toISOString().slice(0,10)).sort((a,b)=>a.date.localeCompare(b.date));}
export async function fetchSeries(item:typeof catalog[number]):Promise<Series>{
 const fetchedAt=new Date().toISOString();
 const start=new Date(Date.now()-400*86400000).toISOString().slice(0,10);
 try {
  let points:Point[]=[];
  if(item.id==='selic'||item.id==='ipca'){
   const response=await fetch(`https://api.bcb.gov.br/dados/serie/bcdata.sgs.${item.code}/dados/ultimos/${item.id==='ipca'?36:180}?formato=json`,{signal:AbortSignal.timeout(12000)});
   if(!response.ok)throw Error('Fonte temporariamente indisponível');
   const data=await response.json() as {data:string;valor:string}[];
   if(!Array.isArray(data))throw Error('Formato inesperado');
   points=data.map(p=>({date:p.data.split('/').reverse().join('-'),value:Number(p.valor)}));
  }else{
   const url=item.id==='eurusd'?`https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=${start}&format=csvdata`:`https://fred.stlouisfed.org/graph/fredgraph.csv?id=${item.code}&cosd=${start}`;
   const response=await fetch(url,{signal:AbortSignal.timeout(25000),headers:{Accept:'text/csv'}});
   if(!response.ok)throw Error('Fonte temporariamente indisponível');
   const rows=csvRows(await response.text());const header=rows.shift()||[];
   const di=item.id==='eurusd'?header.indexOf('TIME_PERIOD'):0;const vi=item.id==='eurusd'?header.indexOf('OBS_VALUE'):1;
   if(di<0||vi<0)throw Error('Formato inesperado');
   points=rows.filter(r=>r[vi]&&r[vi]!=='.').map(r=>({date:r[di],value:Number(r[vi])}));
  }
  points=cleanPoints(points);if(!points.length)throw Error('Sem observações válidas');
  const age=(Date.now()-Date.parse(points.at(-1)!.date))/86400000;
  return {...item,points,status:age>item.maxAge?'desatualizado':'verificado',fetchedAt};
 }catch(error){console.warn('Series unavailable',item.id,error instanceof Error?error.message:'Fetch error');const cached=(snapshot as Record<string,{points:Point[];fetchedAt:string}>)[item.id];if(cached){const points=cleanPoints(cached.points);const age=points.length?(Date.now()-Date.parse(points.at(-1)!.date))/86400000:Infinity;return {...item,points,status:age>item.maxAge?'arquivo desatualizado':'arquivo verificado',error:'Consulta em direto falhou; exibida última recolha arquivada.',fetchedAt:cached.fetchedAt};}return {...item,points:[],status:'indisponível',error:'Não foi possível consultar a fonte. Tente atualizar.',fetchedAt};}
}
export function allocate(budget:number,risk:string,horizon:number){
 if(!Number.isFinite(budget)||budget<=0||budget>1e12||!Number.isFinite(horizon)||horizon<1||horizon>40||!['Conservador','Moderado','Dinâmico'].includes(risk))throw Error('Parâmetros inválidos');
 const weights=horizon<=2?[70,25,5]:risk==='Conservador'?[35,50,15]:risk==='Dinâmico'?[10,20,70]:[20,40,40];
 const amounts=weights.map(w=>Math.round(budget*100*w/100));amounts[0]+=Math.round(budget*100)-amounts.reduce((a,b)=>a+b,0);
 return ['Liquidez e reserva','Obrigações diversificadas','Ações globais diversificadas'].map((name,i)=>({name,weight:weights[i],amount:amounts[i]/100}));
}
export function forecast(points:Point[],steps:number){
 if(points.length<20||steps<1||steps>24)throw Error('São necessárias pelo menos 20 observações');
 const p=points.slice(-120);const changes=p.slice(1).map((x,i)=>x.value-p[i].value);const mean=changes.reduce((a,b)=>a+b,0)/changes.length;
 const sd=Math.sqrt(changes.reduce((a,b)=>a+(b-mean)**2,0)/(changes.length-1));const last=p.at(-1)!.value;
 return Array.from({length:steps+1},(_,i)=>({step:i,base:last,low:last-1.96*sd*Math.sqrt(i),high:last+1.96*sd*Math.sqrt(i)}));
}
