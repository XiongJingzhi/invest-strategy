/* Python lives in a worker: calculations do not freeze the interface. */
importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');
let ready;
async function init(base) {
  const py = await loadPyodide();
  await py.loadPackage(['numpy','pandas','micropip']);
  await py.runPythonAsync(`import micropip\nawait micropip.install(['exchange-calendars==4.11.3'])`);
  py.FS.mkdirTree('/project/invest_strategy');
  for (const file of ['__init__.py','account.py','models.py','performance.py','valuation.py','decision.py','compare.py','research.py','backtest.py','strategies.py','profiles.py']) {
    const response = await fetch(`${base}python/invest_strategy/${file}`);
    if (!response.ok) throw new Error(`无法加载计算模块 ${file}`);
    py.FS.writeFile(`/project/invest_strategy/${file}`, await response.text());
  }
  await py.runPythonAsync(`import sys\nsys.path.insert(0, '/project')\nimport json, io, pandas as pd\nfrom invest_strategy.models import AccountConfig\nfrom invest_strategy.compare import compare_accounts\nfrom invest_strategy.decision import current_decision\nfrom invest_strategy.valuation import FairPEModel, multiplier\n`);
  return py;
}
self.onmessage = async ({data}) => {
  try {
    ready ||= init(data.base);
    const py = await ready;
    py.globals.set('request_json',JSON.stringify(data));
    const output = await py.runPythonAsync(`
req=json.loads(request_json)
market=pd.read_csv(io.StringIO(req['csv']),index_col='date',parse_dates=True)
p=req['params']
weights={'equity':1.0} if p['mode']=='single' else {'equity':.7,'gold':.15,'dividend':.15}
config=AccountConfig(initial_total=p['total'],cash=p['cash'],bonds=p['bonds'],holdings=p['holdings'],reserve=p['reserve'],monthly=p['monthly'],months=p['months'],weights=weights)
if req['action']=='backtest':
    summary, results=compare_accounts(market,p['start'],p['end'],config)
    result={'summary':json.loads(summary.reset_index().to_json(orient='records',date_format='iso')),'daily':{k:json.loads(v.daily.reset_index().to_json(orient='records',date_format='iso')) for k,v in results.items()},'trades':json.loads(results['C'].trades.to_json(orient='records',date_format='iso')),'events':json.loads(results['C'].events.to_json(orient='records',date_format='iso'))}
elif req['action']=='decision':
    ledger=pd.read_csv(io.StringIO(p['ledger'])) if p['ledger'].strip() else None
    d=current_decision(market.ndx.loc[:p['end']],p['start'],p['executionDate'],p['currentCash'],p['currentBonds'],p['remaining'],ledger,config,product_cap=p['cap'])
    d['events']=json.loads(d['events'].to_json(orient='records',date_format='iso'))
    result=json.loads(json.dumps(d,default=str))
elif req['action']=='valuation':
    fair=FairPEModel(p['growth']/100,p['dividend']/100,p['required']/100,p['terminal']).fair_pe()
    q=p['pe']/fair
    result={'fair':fair,'q':q,'multiplier':multiplier(q),'grid':[{'growth':g,'values':[FairPEModel(g/100,p['dividend']/100,r/100,p['terminal']).fair_pe() for r in [p['required']-2,p['required'],p['required']+2]]} for g in [p['growth']-4,p['growth']-2,p['growth'],p['growth']+2,p['growth']+4]]}
json.dumps(result,allow_nan=False)
`);
    self.postMessage({id:data.id,result:JSON.parse(output)});
  } catch (error) { self.postMessage({id:data.id,error:String(error)}); }
};
