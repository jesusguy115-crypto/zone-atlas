"""Shared geometric partitions. Positive world x is the shooter's left."""
import math
LEAGUE='NBA'
def configure(league):
 global LEAGUE
 if league not in {'NBA','CBA'}:raise ValueError(league)
 LEAGUE=league

def classify(row):
 x=-float(row['x_legacy'])/10;y=float(row['y_legacy'])/10
 if LEAGUE=='CBA':
  x*=.3048;y*=.3048;corner,cut,ra,lane,ft=6.6,1.416,1.25,2.45,4.225
 else:corner,cut,ra,lane,ft=22,9.2,4,8,13.75
 if int(row['shot_value'])==3:
  if abs(x)>=corner and y<=cut:return 9 if x<0 else 8
  angle=math.atan2(x,max(y,.003 if LEAGUE=='CBA' else .01))
  return 7 if angle<math.radians(-22) else 5 if angle>math.radians(22) else 6
 if math.hypot(x,y)<=ra:return 0
 if abs(x)<=lane and y<=ft:return 1
 return 4 if x< -lane else 2 if x>lane else 3

def coarse(row):
 i=classify(row)
 return 0 if i==0 else 1 if i==1 else 2 if i<5 else 3 if i<8 else 4
