#!/usr/bin/env python3
"""Normalize cached CBA business data, refusing ambiguous shot/event joins.
league: batch JSONs each contain shootList; player: game catalog + per-game PbP.
No browser credentials or machine-specific paths are needed by this adapter.
"""
import argparse,collections,csv,json,math
from pathlib import Path
TYPES={'2PM','2Pm','3PM','3Pm'}
VERSION='cba-fiba-28x15-v1'
def normalize(r,season,phase):
    if r['pbpType'] not in TYPES:raise ValueError('Unexpected shot type')
    x,y=float(r['shotX']),float(r['shotY'])
    if not all(map(math.isfinite,(x,y))):raise ValueError('Non-finite coordinate')
    # Do not clamp shotY to [0,1]: far heaves can lie beyond half court.
    return dict(season=season,season_type_id=str(phase),game_id=str(r['scheduleId']),person_id=int(r['playerId']),shot_value=int(r['pbpType'][0]),shot_result='Made' if r['pbpType'].endswith('M') else 'Missed',x_legacy=round(-(x-.5)*15/.3048*10,6),y_legacy=round((y*14-1.575)/.3048*10,6),team_id=r['teamId'],source_shotX=x,source_shotY=y)
def align(shots,events):
    """Unique type-preserving subsequence; IDs are source order, clocks playback order.
    Adjacent identical types around a missing event can be ambiguous: stop then.
    """
    events=sorted(events,key=lambda e:int(e['id']))
    if len(events)<len(shots):raise ValueError('Coordinates exceed matching PbP events')
    # Count solutions with a capped DP, then reconstruct only a unique alignment.
    a=[r['pbpType'] for r in shots];b=[e['eventType'] for e in events];n,m=len(a),len(b)
    dp=[[0]*(m+1) for _ in range(n+1)]
    for j in range(m+1):dp[n][j]=1
    for i in range(n-1,-1,-1):
        for j in range(m-1,-1,-1):dp[i][j]=min(2,dp[i][j+1]+(dp[i+1][j+1] if a[i]==b[j] else 0))
    if dp[0][0]!=1:raise ValueError(f'PbP alignment has {dp[0][0]} solutions (2 means multiple); inspect game rather than invent timestamps')
    pairs=[];missing=[];i=j=0
    while j<m:
        if i<n and a[i]==b[j] and dp[i+1][j+1]:pairs.append(events[j]);i+=1
        else:missing.append(events[j])
        j+=1
    return pairs,missing

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['league','player']);ap.add_argument('--batches',type=Path,nargs='+',required=True);ap.add_argument('--season',type=int,required=True,help='End year: 2026 means 2025-26; source uses start year');ap.add_argument('--phase',choices=['2','4'],required=True,help='Normalized regular=2/playoffs=4, not source stageType');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--player-id',type=int);ap.add_argument('--games',type=Path,help='JSON list of {scheduleId,game_date}');ap.add_argument('--pbp-dir',type=Path);ap.add_argument('--official',type=Path,help='Verified selected-scope JSON {fga,fgM,gamesPlayed}');a=ap.parse_args()
    raw=[];seen_games=set()
    for path in a.batches:
        data=json.loads(path.read_text());rs=data['shootList']
        games={str(r['scheduleId']) for r in rs}
        if games&seen_games:raise ValueError('Overlapping game batches: do not duplicate shots or silently dedupe coordinates')
        seen_games|=games;raw.extend(rs)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.mode=='league':
        import pyarrow as pa,pyarrow.parquet as pq
        table=pa.Table.from_pylist([normalize(r,a.season,a.phase) for r in raw]);meta=dict(table.schema.metadata or {});meta.update(league=b'CBA',geometry_version=VERSION.encode());pq.write_table(table.replace_schema_metadata(meta),a.output)
        print(json.dumps({'league':'CBA','geometry_version':VERSION,'games':len(seen_games),'attempts':len(raw)}));return
    if not all([a.player_id,a.games,a.pbp_dir,a.official]):ap.error('Player mode requires player-id, games, pbp-dir, official')
    games={str(g['scheduleId']):g for g in json.loads(a.games.read_text())};grouped=collections.defaultdict(list)
    for r in raw:
        if int(r['playerId'])==a.player_id:grouped[str(r['scheduleId'])].append(r)
    order={gid:i+1 for i,gid in enumerate(sorted(games,key=lambda k:(games[k]['game_date'],k)))};rows=[];unmatched=[]
    for gid,rs in grouped.items():
        data=json.loads((a.pbp_dir/f'{gid}.json').read_text())
        # A player-filtered cache may only be reused for that exact player.
        if data.get('scope')=='player' and int(data['player_id'])!=a.player_id:raise ValueError('Wrong player-specific PbP cache')
        ev=[e for e in data['records'] if e['eventType'] in TYPES and int(e.get('playerId',data.get('player_id',-1)))==a.player_id]
        pairs,extra=align(rs,ev);unmatched.extend(dict(game_id=gid,event=e) for e in extra)
        for r,e in zip(rs,pairs):
            row=normalize(r,a.season,a.phase);row.update(game_date=games[gid]['game_date'],period=e['quarter'],clock=e['eventTime'],game_number=order[gid],event_id=e['id'],description=e['eventType']);rows.append(row)
    def remaining(s):
        mm,ss=s.split(':');return int(mm)*60+float(ss)
    rows.sort(key=lambda r:(r['game_date'],r['game_id'],int(r['period']),-remaining(r['clock']),int(r['event_id'])))
    if not rows:raise ValueError('Player has no coordinate-backed shots')
    official=json.loads(a.official.read_text());made=sum(r['shot_result']=='Made' for r in rows);gap=int(official['fga'])-len(rows);made_gap=int(official['fgM'])-made
    if gap<0 or made_gap<0 or made_gap>gap:raise ValueError('Coordinate/official totals conflict: check player, season, phase, revisions')
    # Also inspect scheduled games with no coordinates; they may contain omitted attempts.
    checked=set(grouped)
    for gid in set(games)-checked:
        path=a.pbp_dir/f'{gid}.json'
        if not path.exists():raise ValueError(f'Need PbP for unplotted game {gid}')
        d=json.loads(path.read_text());unmatched.extend(dict(game_id=gid,event=e) for e in d['records'] if e['eventType'] in TYPES and int(e.get('playerId',d.get('player_id',-1)))==a.player_id)
    if gap!=len(unmatched) or made_gap!=sum(e['event']['eventType'].endswith('M') for e in unmatched):raise ValueError('Season discrepancy not fully explained by verified missing-coordinate events')
    with a.output.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    audit={'league':'CBA','geometry_version':VERSION,'player_id':a.player_id,'expected_attempts':len(rows),'expected_made':made,'expected_games':len(grouped),'official_attempts':int(official['fga']),'official_made':int(official['fgM']),'official_games':int(official['gamesPlayed']),'missing_coordinate_attempts':gap,'unmatched_events':unmatched,'all_coordinate_rows_preserved':True}
    a.output.with_suffix('.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print(json.dumps(audit,ensure_ascii=False))
if __name__=='__main__':main()
