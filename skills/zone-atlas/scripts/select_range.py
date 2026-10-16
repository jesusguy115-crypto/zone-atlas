#!/usr/bin/env python3
"""Select one player's actual appearance range, preserving zero-FGA games in numbering."""
import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--shots',type=Path,required=True);p.add_argument('--player-id',type=int,required=True);p.add_argument('--seasons',nargs='+',type=int,required=True,help='Season end years');p.add_argument('--phases',nargs='+',choices=['2','4'],required=True);p.add_argument('--games',type=Path,help='Official appearance catalog JSON; required for ordinal ranges');p.add_argument('--first-game',type=int);p.add_argument('--last-game',type=int);p.add_argument('--game-ids',nargs='+');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.shots.suffix=='.parquet':
 import pyarrow.parquet as pq
 rows=pq.read_table(a.shots).to_pylist()
else:rows=list(csv.DictReader(a.shots.open(encoding='utf-8-sig')))
rows=[r for r in rows if int(r['person_id'])==a.player_id and int(r['season']) in a.seasons and str(r['season_type_id']) in a.phases]
if not rows:raise ValueError('No coordinate shots in player/season/phase scope')
ordinal=a.first_game is not None or a.last_game is not None
if ordinal and a.game_ids:raise ValueError('Choose ordinal range or explicit game IDs')
if ordinal and not a.games:raise ValueError('Ordinal ranges require official appearance catalog, including zero-FGA appearances; do not number only games with coordinates')
if a.games:
 catalog=json.loads(a.games.read_text())
 games=[g for g in catalog if int(g['person_id'])==a.player_id and int(g['season']) in a.seasons and str(g['season_type_id']) in a.phases and g['played'] is True]
 games.sort(key=lambda g:(g['game_date'],str(g['game_id'])))
 if len({str(g['game_id']) for g in games})!=len(games):raise ValueError('Duplicate appearance IDs')
 if not {str(r['game_id']) for r in rows}<={str(g['game_id']) for g in games}:raise ValueError('Appearance catalog does not cover coordinate games')
else:
 if any(not r.get('game_date') for r in rows):raise ValueError('Join schedule game_date before selection, or provide appearance catalog')
 dates={str(r['game_id']):r['game_date'] for r in rows};games=[{'game_id':gid,'game_date':dt} for gid,dt in sorted(dates.items(),key=lambda kv:(kv[1],kv[0]))]
if ordinal:
 first=a.first_game or 1;last=a.last_game or len(games)
 if first<1 or last<first or last>len(games):raise ValueError(f'Range must be within 1..{len(games)} actual appearances')
 games=games[first-1:last]
if a.game_ids:
 wanted=set(a.game_ids);games=[g for g in games if str(g['game_id']) in wanted]
 if {str(g['game_id']) for g in games}!=wanted:raise ValueError('Requested game IDs outside player/season/phase scope')
ids={str(g['game_id']) for g in games};rows=[r for r in rows if str(r['game_id']) in ids]
if not rows:raise ValueError('Selected range has no coordinate shots')
dates={str(g['game_id']):g['game_date'] for g in games}
for r in rows:r['game_date']=dates[str(r['game_id'])]
rows.sort(key=lambda r:(r['game_date'],str(r['game_id'])))
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
report={'player_id':a.player_id,'selected_game_ids':[str(g['game_id']) for g in games],'games':len(games),'coordinate_games':len({str(r['game_id']) for r in rows}),'attempts':len(rows),'made':sum(r['shot_result']=='Made' for r in rows),'range':[a.first_game,a.last_game],'seasons':a.seasons,'phases':a.phases,'first_date':games[0]['game_date'],'last_date':games[-1]['game_date'],'ordinal_basis':'actual appearances including zero-FGA' if a.games else 'coordinate-bearing games; no ordinal range used'}
a.output.with_suffix('.selection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
