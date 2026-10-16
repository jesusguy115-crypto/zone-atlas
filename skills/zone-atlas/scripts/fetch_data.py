#!/usr/bin/env python3
"""Fetch selected NBA shot seasons and join schedule dates. No account or token needed."""
import argparse,csv,json,re,time,urllib.request
from pathlib import Path
API='https://api.github.com/repos/sportsdataverse/sportsdataverse-data/releases/tags/'
def get(url,path):
 if path.exists():return path
 req=urllib.request.Request(url,headers={'User-Agent':'nba-shot-atlas'})
 for attempt in range(3):
  try:
   with urllib.request.urlopen(req,timeout=90) as response:path.with_suffix(path.suffix+'.part').write_bytes(response.read())
   path.with_suffix(path.suffix+'.part').replace(path);return path
  except Exception:
   if attempt==2:raise
   time.sleep(2*(attempt+1))
def manifest(cache,tag,refresh=False):
 path=cache/(tag+'.json')
 if refresh and path.exists():path.unlink()
 get(API+tag,path);d=json.loads(path.read_text());return {a['name']:a['browser_download_url'] for a in d['assets']}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--person-id',type=int);ap.add_argument('--years',default='all',help='Season END years, e.g. 1998,2026 or all');ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--output',type=Path);ap.add_argument('--list-seasons',action='store_true');ap.add_argument('--refresh',action='store_true');args=ap.parse_args();args.cache.mkdir(parents=True,exist_ok=True)
 shots=manifest(args.cache,'nba_stats_shots',args.refresh);available=sorted(int(re.fullmatch(r'shots_(\d{4})\.parquet',n)[1]) for n in shots if re.fullmatch(r'shots_(\d{4})\.parquet',n))
 if args.list_seasons:print(json.dumps({'end_years':available,'labels':[f'{y-1}-{str(y)[-2:]}' for y in available]}));return
 if args.person_id is None or args.output is None:ap.error('--person-id and --output are required for extraction')
 import pyarrow.parquet as pq
 import pyarrow.compute as pc
 years=available if args.years=='all' else [int(y) for y in args.years.split(',')]
 schedules=manifest(args.cache,'nba_stats_schedules',args.refresh);allrows=[];report=[]
 for year in years:
  name=f'shots_{year}.parquet'
  if name not in shots:raise ValueError(f'Season {year} is not published; never invent missing seasons.')
  table=pq.read_table(get(shots[name],args.cache/name));table=table.filter(pc.equal(table['person_id'],args.person_id));rows=[r for r in table.to_pylist() if str(r['season_type_id']) in {'2','4'}]
  if not rows:report.append({'season_end_year':year,'attempts':0,'status':'no_player_shots'});continue
  candidates=[n for n in schedules if n.endswith('.parquet') and re.search(rf'(^|_){year}\.parquet$',n)]
  if len(candidates)!=1:raise ValueError(f'Cannot uniquely identify schedule parquet for {year}: {candidates}')
  sn=candidates[0];schedule={str(r['game_id']):r for r in pq.read_table(get(schedules[sn],args.cache/sn)).to_pylist()}
  for r in rows:
   info=schedule.get(str(r['game_id']))
   if not info or not info.get('game_date'):raise ValueError(f'Missing date for {r["game_id"]}')
   r.update(game_date=str(info['game_date'])[:10],matchup=info.get('matchup',''))
  allrows.extend(rows);report.append({'season_end_year':year,'attempts':len(rows),'games':len({r['game_id'] for r in rows}),'status':'loaded'})
 def remaining(clock):
  m=re.fullmatch(r'PT(?:(\d+)M)?([\d.]+)S',str(clock));return float(m[1] or 0)*60+float(m[2]) if m else float(clock.split(':')[0])*60+float(clock.split(':')[1])
 allrows.sort(key=lambda r:(r['game_date'],str(r['game_id']),int(r['period']),-remaining(r['clock'])))
 games=sorted({(r['game_date'],str(r['game_id'])) for r in allrows});number={g:i+1 for i,g in enumerate(games)}
 for r in allrows:r['game_number']=number[(r['game_date'],str(r['game_id']))]
 if not allrows:raise ValueError('No shots in selected seasons.')
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with args.output.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
 args.output.with_suffix('.coverage.json').write_text(json.dumps({'person_id':args.person_id,'requested_years':years,'seasons':report,'attempts':len(allrows),'made':sum(r['shot_result']=='Made' for r in allrows)},ensure_ascii=False,indent=2))
 print(json.dumps({'file':str(args.output),'attempts':len(allrows),'games':len(games),'coverage':report},ensure_ascii=False))
if __name__=='__main__':main()
