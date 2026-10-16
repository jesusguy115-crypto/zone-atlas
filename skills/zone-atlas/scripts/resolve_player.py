#!/usr/bin/env python3
import argparse,json,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def normalize(s):
 s=''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if not unicodedata.combining(c))
 return re.sub(r'[^\w\u3400-\u9fff]','',s).replace('_','')
def resolve(name,catalog=None):
 catalog=catalog or json.loads((ROOT/'assets/players.json').read_text());key=normalize(name);found=[]
 for p in catalog:
  if key in {normalize(n) for n in [p['name_en'],p['name_zh'],*p['aliases']]}:found.append(p)
 # Catalog is deliberately incomplete; unknown means research, not a guessed match.
 return {'status':'resolved' if len(found)==1 else ('ambiguous' if found else 'needs_verified_lookup'),'input':name,'candidates':found,'id_namespace':'NBA person_id (not ESPN player id)'}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('name');args=ap.parse_args();print(json.dumps(resolve(args.name),ensure_ascii=False,indent=2))
