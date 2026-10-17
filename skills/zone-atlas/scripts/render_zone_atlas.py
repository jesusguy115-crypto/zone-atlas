#!/usr/bin/env python3
"""Append an expanding sidebar-background reveal and a coordinate-derived zone chart."""
from pathlib import Path
from functools import lru_cache
import argparse,csv,json,math,subprocess,os
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from safe_area import image as safe_image,settings as safe_settings

NAMES=['篮下','禁区短两分','左侧中距离','正面中距离','右侧中距离','左翼三分','弧顶三分','右翼三分','左底角三分','右底角三分']
from zone_geometry import configure, classify

def ease(t):
 t=max(0.,min(1.,t));return t*t*(3-2*t)


from datetime import date
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--shots',type=Path,required=True);ap.add_argument('--league-shots',type=Path,nargs='+',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
p=a.job.resolve().parent;work=a.output.resolve();work.mkdir(parents=True,exist_ok=True)
job=json.loads(a.job.read_text());job['season_label']=job['season_label'].replace('—','-').replace('–','-');job['baseline_label']=job['baseline_label'].replace('—','-').replace('–','-')
if job['league'] not in {'NBA','CBA'}:raise ValueError('NBA or CBA required')
if safe_settings(job)!=(96,144):raise ValueError('This approved layout uses 96/144 bands; reflow coordinates before changing dimensions')
configure(job['league'])
rows=list(csv.DictReader(a.shots.open(encoding='utf-8-sig')))
if not rows or {int(r['person_id']) for r in rows}!={int(job['player_id'])}:raise ValueError('Expected selected shots for exactly this player')
if any(r['shot_result'] not in {'Made','Missed'} or int(r['shot_value']) not in {2,3} for r in rows):raise ValueError('Only FGA rows allowed')
for r in rows:
 if not all(math.isfinite(float(r[k])) for k in ['x_legacy','y_legacy']):raise ValueError('Nonfinite coordinate')
ids={str(r['game_id']) for r in rows}
if 'selected_game_ids' in job:
 if not ids<=set(map(str,job['selected_game_ids'])):raise ValueError('Shot outside selected game scope')
 if len(set(map(str,job['selected_game_ids'])))!=job['expected_games']:raise ValueError('Selected game catalog count mismatch')
elif len(ids)!=job['expected_games']:raise ValueError('Expected games mismatch; zero-FGA games require selected_game_ids')
if len(rows)!=job['expected_attempts'] or sum(r['shot_result']=='Made' for r in rows)!=job['expected_made']:raise ValueError('Coordinate counts disagree with explicit job totals')
W,H,S,SIDEBAR=1920,1080,2,736;BG=(25,25,27)
age=None
if job.get('birth_date'):
 born=date.fromisoformat(job['birth_date']);asof=date.fromisoformat(job['age_as_of']);age=asof.year-born.year-((asof.month,asof.day)<(born.month,born.day))
if (age is not None and age<0) or (job.get('league_season_number') is not None and job['league_season_number']<1):raise ValueError('Invalid age or league season number')
@lru_cache(None)
def font(n,weight='regular'):
 name='BarlowCondensed-Bold.ttf' if weight=='number' else 'NotoSansSC.ttf'
 f=ImageFont.truetype(str(ROOT/'assets/fonts'/name),round(n*S))
 if name=='NotoSansSC.ttf':
  try:f.set_variation_by_axes([700 if weight=='bold' else 450])
  except (OSError,ValueError):pass
 return f
def text(im,pos,s,n,color,weight='regular',anchor='mm'):
 ImageDraw.Draw(im).text(tuple(v*S for v in pos),s,font=font(n,weight),fill=color,anchor=anchor)
def line(im,points,color,width=1):ImageDraw.Draw(im).line([(x*S,y*S) for x,y in points],fill=color,width=max(1,round(width*S)),joint='curve')
def poly(im,points,fill,outline=None,width=1):ImageDraw.Draw(im).polygon([(x*S,y*S) for x,y in points],fill=fill,outline=outline,width=max(1,round(width*S)))
def arc_points(x,y,r,t0,t1,n=100):return [(x+r*math.cos(t),y+r*math.sin(t)) for t in np.linspace(t0,t1,n)]

side=Image.new('RGB',(SIDEBAR*S,H*S),BG)
def st(x,y,t,size=23,col='#f2eee8',weight='regular',anchor='la'):
 text(side,(x,y),t,size,col,weight,anchor)
def hline(y):line(side,[(48,y),(686,y)],'#414144',.8)
portrait=Image.open(p/job['portrait_image']).convert('RGBA').crop(tuple(job['portrait_crop']));portrait.thumbnail((140*S,160*S),Image.Resampling.LANCZOS);side.paste(portrait,(35*S,104*S),portrait)
# Name, English secondary title, then a quiet four-column metric row.
zh_size=48
zh=ImageFont.truetype(str(ROOT/'assets/fonts/SmileySans-Oblique.ttf'),zh_size*S)
while zh.getlength(job['name_zh'])>480*S and zh_size>26:
 zh_size-=1;zh=ImageFont.truetype(str(ROOT/'assets/fonts/SmileySans-Oblique.ttf'),zh_size*S)
ImageDraw.Draw(side).text((197*S,108*S),job['name_zh'],font=zh,fill='#f2eee8')
# Normal-width Latin lettering, with measured tracking instead of condensed numerals.
en_font=ImageFont.truetype(str(ROOT/'assets/fonts/NotoSansSC.ttf'),24*S)
try:en_font.set_variation_by_axes([600])
except (OSError,ValueError):pass
en_x=200*S;en_tracking=2.0*S
for ch in job['name_en']:
 ImageDraw.Draw(side).text((round(en_x),166*S),ch,font=en_font,fill='#a39fa2',anchor='la')
 en_x+=en_font.getlength(ch)+en_tracking
for j,(label,value) in enumerate([('身高',(f"{job['height_cm']:g} cm" if job.get('height_cm') is not None else '—')),('体重',(f"{job['weight_kg']:g} kg" if job.get('weight_kg') is not None else '—')),('年龄',str(age) if age is not None else '—'),(job['league']+'球龄',str(job['league_season_number']) if job.get('league_season_number') else '—')]):
 x=202+j*121
 st(x,205,label,14,'#9e999d');st(x,229,value,23,'#e1dfe0','bold')
 if j<3:line(side,[(x+105,209),(x+105,254)],'#343437',.7)
hline(281)
# Compact date-only band; the space saved gives the region rows more air.
date_label=job['date_label']
if '—' in date_label:
 left,right=map(str.strip,date_label.split('—',1))
 if len(right)==5 and len(left)>=10:right=left[:5]+right
 date_label=left+' — '+right
st(48,304,'比赛日期：'+date_label,18,'#c6c2c5')
hline(345)
# Four independent columns: attempts, makes, misses, FG percentage.
st(48,374,job.get('attempt_label','坐标出手' if job.get('missing_coordinate_attempts',0) else '出手'),19,'#aaa6a9')
poly(side,[(220,382),(229,382),(229,391),(220,391)],'#e52b4a');st(239,374,'命中',19,'#aaa6a9')
poly(side,[(386,382),(395,382),(395,391),(386,391)],'#ede9e3');st(405,374,'未中',19,'#aaa6a9')
st(550,374,'投篮命中率',19,'#aaa6a9')
for x in [194,360,524]:line(side,[(x,376),(x,467)],'#353437',.8)
st(48,414,str(len(rows)),54,weight='number')
st(220,414,str(job['expected_made']),54,weight='number')
st(386,414,str(len(rows)-job['expected_made']),54,weight='number')
st(550,414,f"{100*job['expected_made']/len(rows):.1f}%",54,weight='number')
hline(490)
st(48,500,'投篮区域',29,weight='bold');st(683,509,'命中 / 出手',18,'#bdb8bb',anchor='ra')
# Sidebar uses the same five rules as the ten-zone court.
from zone_geometry import coarse as zone
coarse_side=np.zeros((5,2),int)
for r in rows:coarse_side[zone(r),0 if r['shot_result']=='Made' else 1]+=1
names=['篮下','短两分','长两分','弧顶及侧翼三分','底角三分'];scale=max(coarse_side.sum(1));max_width=635
for i,(label,(m,miss)) in enumerate(zip(names,coarse_side)):
 y=548+i*80;n=int(m+miss);st(48,y,label,23,weight='bold');st(683,y-2,f'{m} / {n}',28,weight='number',anchor='ra')
 width=max_width*n/scale if n else 0;by=(y+38)*S;bh=14*S
 if n:
  mask=Image.new('L',(round(width*S),bh));ImageDraw.Draw(mask).rounded_rectangle((0,0,mask.width-1,bh-1),radius=bh/2,fill=255)
  bar=Image.new('RGB',mask.size,'#eeeae5');red=round(mask.width*m/n)
  ImageDraw.Draw(bar).rectangle((0,0,max(0,red-1),bh),fill='#ed314d') if red else None
  # Soft continuous gloss, clipped to the rounded capsule.
  ar=np.asarray(bar).copy().astype(float)
  for yy in range(bh):ar[yy]=np.clip(ar[yy]+18*np.exp(-((yy-bh*.2)/(bh*.26))**2)-7*yy/bh,0,255)
  side.paste(Image.fromarray(ar.astype('uint8')),(48*S,by),mask)
 label_width=font(23,'bold').getlength(label)/S
 st(48+label_width+18,y+7,f'{100*m/n:.1f}%' if n else '—',17,'#a9a3a7')
# Baseline remains in audit and delivery description; no extra text in subtitle band.
frozen_left=side.resize((SIDEBAR,H),Image.Resampling.LANCZOS)
counts=np.zeros((10,2),dtype=int)
for row in rows:counts[classify(row),0 if row['shot_result']=='Made' else 1]+=1
assert counts.sum()==len(rows)==job['expected_attempts'] and counts[:,0].sum()==job['expected_made']
# The ten spatial zones partition the original five categories exactly.
from zone_geometry import coarse as zone
coarse=np.zeros((5,2),dtype=int)
for row in rows:coarse[zone(row),0 if row['shot_result']=='Made' else 1]+=1
reconstructed=np.stack([counts[0],counts[1],counts[2:5].sum(0),counts[5:8].sum(0),counts[8:10].sum(0)])
assert np.array_equal(coarse,reconstructed)
# Compute same-season, same-phase league baselines with identical geometry.
import pyarrow.parquet as pq
phases={str(r['season_type_id']) for r in rows};seasons={int(r['season']) for r in rows}
league=np.zeros((10,2),dtype=int)
required={(int(r['season']),str(r['season_type_id'])) for r in rows};baseline_ids=set(map(str,job.get('baseline_game_ids',[])))
covered=set();seen_files=set()
for league_path in a.league_shots:
 resolved=league_path.resolve()
 if resolved in seen_files:raise ValueError('Duplicate league parquet input')
 seen_files.add(resolved)
 table=pq.read_table(resolved,columns=['season','season_type_id','game_id','shot_value','shot_result','x_legacy','y_legacy'])
 if job['league']=='NBA' and (table.schema.metadata or {}).get(b'league')==b'CBA':raise ValueError('CBA league data cannot be used for NBA')
 if job['league']=='CBA' and (table.schema.metadata or {}).get(b'league')!=b'CBA':raise ValueError('Use verified CBA league parquet, not NBA data')
 for r in table.to_pylist():
  if (int(r['season']),str(r['season_type_id'])) in required and (not baseline_ids or str(r['game_id']) in baseline_ids):
   covered.add((int(r['season']),str(r['season_type_id'])))
   league[classify(r),0 if r['shot_result']=='Made' else 1]+=1
if covered!=required:raise ValueError(f'Missing league season/phase data: {sorted(required-covered)}')
assert (league.sum(1)>0).all()
league_pct=100*league[:,0]/league.sum(1)
player_pct=np.divide(100*counts[:,0],counts.sum(1),out=np.zeros(10),where=counts.sum(1)>0)
delta=player_pct-league_pct
palette=['#30a6d2','#8bd3e5','#d4d4d1','#f3bd39','#f23859']
def color(i):return palette[2] if counts[i].sum()==0 else palette[0 if delta[i]<-5 else 1 if delta[i]<-2 else 2 if delta[i]<=2 else 3 if delta[i]<=5 else 4]
(work/'分区数据.json').write_text(json.dumps({'rows':[{'区域':NAMES[i],'命中':int(v[0]),'出手':int(v.sum()),'命中率':round(float(player_pct[i]),2),'联盟命中':int(league[i,0]),'联盟出手':int(league[i].sum()),'联盟命中率':round(float(league_pct[i]),2),'较联盟百分点':round(float(delta[i]),2),'颜色':color(i)} for i,v in enumerate(counts)],'league_source':[str(v) for v in a.league_shots],'season_types':sorted(phases),'note':'球员与同赛季联盟同区域加权命中率比较；几何区域及赛事口径一致；左右以球员面向篮筐为准（图面右=球员左）。六边形颜色为区域效率，大小为坐标出手频次。','aggregate_matches_sidebar':True},ensure_ascii=False,indent=2))

# Half-court summary is diagrammatic, with the same charcoal as the sidebar.
chart=Image.new('RGB',(W*S,H*S),BG)
# Removed right-side chart heading at user request.
# No top-right team logo; retain only the subtle court watermark.
CX=1330;BASE=900;K=16.0 if job['league']=='CBA' else 16.0
FIBA=job['league']=='CBA'
WIDTH=15/.3048 if FIBA else 50
INSET=1.575/.3048 if FIBA else 5.25
LENGTH=14/.3048 if FIBA else 47
LANE=2.45/.3048 if FIBA else 8
FT=4.225/.3048 if FIBA else 13.75
RA=1.25/.3048 if FIBA else 4
THREE=6.75/.3048 if FIBA else 23.75
CORNER=6.6/.3048 if FIBA else 22
def xy(x,y):return CX+x*K,BASE-(y+INSET)*K
# Subtle team watermark below the data.
mark=Image.open(p/job['logo_image']).convert('RGBA');mark.thumbnail((270*S,160*S),Image.Resampling.LANCZOS);mark.putalpha(mark.getchannel('A').point(lambda v:round(v*.065)))
chart.paste(mark,(round(CX*S-mark.width/2),round(580*S)),mark)

# Size is location frequency; color is the matching region's FG% difference from league.
bins={};radius=.68
for row in rows:
 x=-float(row['x_legacy'])/10;y=float(row['y_legacy'])/10
 qf=(math.sqrt(3)/3*x-y/3)/radius;rf=(2*y/3)/radius
 # Cube-coordinate nearest-cell rounding on a pointy hexagonal grid.
 cx=qf;cz=rf;cy=-cx-cz;rx,ry,rz=round(cx),round(cy),round(cz)
 dx,dy,dz=abs(rx-cx),abs(ry-cy),abs(rz-cz)
 if dx>dy and dx>dz:rx=-ry-rz
 elif dy>dz:ry=-rx-rz
 else:rz=-rx-ry
 key=(rx,rz,classify(row));bins[key]=bins.get(key,0)+1
max_bin=max(bins.values())
for (q,r,zi),n in bins.items():
 wx=radius*math.sqrt(3)*(q+r/2);wy=radius*1.5*r;px,py=xy(wx,wy)
 rr=3.0+8.0*(math.log1p(n)/math.log1p(max_bin))**.6
 pts=arc_points(px,py,rr,math.pi/6,2*math.pi+math.pi/6,7)[:-1]
 poly(chart,pts,color(zi),'#e4ded7',.5)

ink='#bbb7ba';soft='#6d696e'
for seg in [[(-WIDTH/2,-INSET),(WIDTH/2,-INSET)], [(-WIDTH/2,-INSET),(-WIDTH/2,LENGTH-INSET)],[(WIDTH/2,-INSET),(WIDTH/2,LENGTH-INSET)],[(-WIDTH/2,LENGTH-INSET),(WIDTH/2,LENGTH-INSET)]]:line(chart,[xy(*v) for v in seg],ink,1.25)
line(chart,[xy(-LANE,-INSET),xy(-LANE,FT),xy(LANE,FT),xy(LANE,-INSET)],ink,1.2)
line(chart,[xy(*v) for v in arc_points(0,FT,1.8/.3048 if FIBA else 6,0,math.pi)],ink,1.15)
# Restricted area and backboard/rim.
line(chart,[xy(*v) for v in arc_points(0,0,RA,0,math.pi)],'#d0c9cc',1.25)
line(chart,[xy(-3,-1.25),xy(3,-1.25)],'#e4dce0',2.)
line(chart,[xy(*v) for v in arc_points(0,0,.75,0,2*math.pi)],'#d8a1ab',1.4)
cutoff=math.sqrt(THREE**2-CORNER**2);theta=math.atan2(cutoff,CORNER)
line(chart,[xy(-CORNER,-INSET),xy(-CORNER,cutoff)],ink,1.35);line(chart,[xy(CORNER,-INSET),xy(CORNER,cutoff)],ink,1.35)
line(chart,[xy(*v) for v in arc_points(0,0,THREE,theta,math.pi-theta)],ink,1.35)
# The extra spatial subdivisions remain quiet and follow coordinate boundaries.
for x in [-LANE,LANE]:line(chart,[xy(x,FT),xy(x,math.sqrt(THREE**2-x*x))],soft,.7)
for sg in [-1,1]:
 angle=math.pi/2+sg*math.radians(22)
 line(chart,[xy(THREE*math.cos(angle),THREE*math.sin(angle)),xy((LENGTH-INSET)/math.sin(angle)*math.cos(angle),LENGTH-INSET)],soft,.7)
# Compact reference-style legends: efficiency colors and shot frequency sizes.
text(chart,(1134,921),'低于均值',12,palette[0],'bold','lm')
for j,c in enumerate(palette):
 poly(chart,arc_points(1201+j*17,921,7.2,math.pi/6,2*math.pi+math.pi/6,7)[:-1],c,'#e9e4df',.6)
text(chart,(1287,921),'高于均值',12,palette[-1],'bold','lm')
text(chart,(1399,921),'出手频次',12,'#bdb9bc','regular','lm')
for j,r in enumerate([3,4.8,7.2,9.6]):poly(chart,arc_points(1462+j*18,921,r,math.pi/6,2*math.pi+math.pi/6,7)[:-1],'#c9c7c5')
# Labels sit within their corresponding spatial areas; the rim uses a short callout.
placements=[(10.8,-.2),(0,8.5),(15.2,11.0),(0,19.4),(-15.2,11.0),(18.2,27.5),(0,33.7),(-18.2,27.5),(23.5,2.7),(-23.5,2.7)]
cards=[]
for i,((wx,wy),value) in enumerate(zip(placements,counts)):
 m=int(value[0]);n=int(value.sum());pct=100*m/n if n else 0;px,py=xy(wx,wy)
 lay=Image.new('RGBA',(W*S,H*S));draw=ImageDraw.Draw(lay)
 draw.rounded_rectangle(((px-76)*S,(py-44)*S,(px+76)*S,(py+47)*S),radius=10*S,fill=(25,25,27,237))
 text(lay,(px,py-29),NAMES[i],14,'#aaa2a6')
 text(lay,(px,py+1),f'{pct:.1f}%' if n else '—',35,color(i),'number')
 text(lay,(px,py+32),f'{m} / {n}',20,'#dfd8da','number')
 cards.append(lay)
# The restricted-area annotation is offset slightly to preserve the visible hoop.
line(chart,[xy(1.9,1.6),xy(5.4,1.6),xy(7.0,.3)],'#a9868d',.75)
full=chart.convert('RGBA')
for card in cards:full=Image.alpha_composite(full,card)
full.paste(side,(0,0));full=full.convert('RGB');shift=round(job.get('layout_offset_x',69)*S);shifted=Image.new('RGB',full.size,BG);shifted.paste(full,(shift,0));full=shifted;top,bottom=safe_settings(job);full.save(work/'区域投篮_4K.png');full.resize((W,H),Image.Resampling.LANCZOS).save(work/'总结页.png')

report={'job':job,'attempts':len(rows),'made':job['expected_made'],'games':job['expected_games'],'age_at_scope':age,'all_coordinate_records_retained':True,'geometry':job['league'],'output':'区域投篮_4K.png','safe_area':{'top_at_1080':top,'bottom_at_1080':bottom,'layout':'reflow_full_width','horizontal_offset':job.get('layout_offset_x',69)}}
(work/'制作核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(work/'区域投篮_4K.png')
