import {parseMarket,compare,decision,valuation} from './engine.js';
let calendar;
self.onmessage=async ({data})=>{try{let result;if(data.action==='valuation')result=valuation(data.params);else{const market=parseMarket(data.csv);if(data.action==='decision')result=decision(market,data.params);else{if(!calendar){const r=await fetch(`${data.base}data/xnys.json`);if(!r.ok)throw Error('无法加载交易日历');calendar=await r.json()}result=compare(market,data.params,calendar)}}self.postMessage({id:data.id,result})}catch(error){self.postMessage({id:data.id,error:String(error.message||error)})}};
