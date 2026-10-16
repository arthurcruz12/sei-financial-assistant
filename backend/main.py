"""Standalone FastAPI research service. The published Sites app uses its Worker API.
No trade execution, generated probabilities or hard-coded market prices.
"""
import asyncio
import csv
import io
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Literal
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title='SEI Research API', version='0.1.0', description='Public economic observations and explicit exploratory models.')

class PortfolioInput(BaseModel):
    budget: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    risk: Literal['Conservador', 'Moderado', 'Dinâmico'] = 'Moderado'
    horizon: int = Field(default=5, ge=1, le=40)

class ForecastInput(BaseModel):
    values: list[float] = Field(min_length=20, max_length=10000)
    steps: int = Field(default=12, ge=1, le=24)

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'SEI research', 'version': '0.1.0'}

@app.post('/portfolio')
def portfolio(p: PortfolioInput):
    weights = [70,25,5] if p.horizon <= 2 else {'Conservador':[35,50,15], 'Moderado':[20,40,40], 'Dinâmico':[10,20,70]}[p.risk]
    cents = round(p.budget * 100)
    amounts = [round(cents * w / 100) for w in weights]
    amounts[0] += cents - sum(amounts)
    return {'method':'fixed educational allocation v1', 'simulation':True, 'allocation':[{'name':n,'weight':w,'amount':a/100} for n,w,a in zip(['Liquidez e reserva','Obrigações diversificadas','Ações globais diversificadas'],weights,amounts)]}

@app.post('/forecast')
def forecast(p: ForecastInput):
    if not all(math.isfinite(v) for v in p.values):
        raise HTTPException(422, 'All observations must be finite')
    values = p.values[-120:]
    sd = statistics.stdev([b-a for a,b in zip(values,values[1:])])
    return {'method':'random walk without drift; normal approximation', 'validated':False, 'steps':[{'step':i,'base':values[-1],'low':values[-1]-1.96*sd*math.sqrt(i),'high':values[-1]+1.96*sd*math.sqrt(i)} for i in range(p.steps+1)]}

@app.get('/markets')
async def markets():
    since = (date.today()-timedelta(days=400)).isoformat()
    specs = [('fedfunds','DFF'),('liquidity','WALCL'),('stress','STLFSI4')]
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        async def read(identifier, code):
            source = f'https://fred.stlouisfed.org/series/{code}'
            try:
                response = await client.get(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd={since}')
                response.raise_for_status()
                rows = list(csv.reader(io.StringIO(response.text)))[1:]
                points = [{'date':r[0],'value':float(r[1])} for r in rows if len(r)>1 and r[1] not in ('','.') and date.fromisoformat(r[0]) <= date.today() and math.isfinite(float(r[1]))]
                if not points:
                    raise ValueError('No valid observations')
                return {'id':identifier,'source':source,'points':points,'status':'observed'}
            except (httpx.HTTPError, ValueError, IndexError):
                return {'id':identifier,'source':source,'points':[],'status':'unavailable'}
        return {'fetchedAt':datetime.now(timezone.utc).isoformat(),'series':await asyncio.gather(*(read(*s) for s in specs))}
