#!/usr/bin/env python3
"""Reserve clean top/logo and bottom/subtitle bands without cropping content."""
from pathlib import Path
import argparse,json,subprocess
from PIL import Image
TOP=96;BOTTOM=144;REFERENCE_H=1080;BG=(25,25,27)
def settings(job=None):
 area=(job or {}).get('safe_area',{})
 return int(area.get('top',TOP)),int(area.get('bottom',BOTTOM))
def image(im,top=TOP,bottom=BOTTOM):
 w,h=im.size;t=round(top*h/REFERENCE_H);b=round(bottom*h/REFERENCE_H)
 if t<0 or b<0 or t+b>=h:raise ValueError('Invalid safe area')
 body_h=h-t-b;scale=body_h/h;body_w=round(w*scale)
 out=Image.new('RGB',(w,h),BG);out.paste(im.convert('RGB').resize((body_w,body_h),Image.Resampling.LANCZOS),((w-body_w)//2,t));return out

def video_filter(width=1920,height=1080,top=TOP,bottom=BOTTOM):
 t=round(top*height/REFERENCE_H);b=round(bottom*height/REFERENCE_H);body_h=(height-t-b)//2*2
 if t<0 or b<0 or body_h<=0:raise ValueError('Invalid safe area')
 return f'scale=-2:{body_h}:flags=lanczos,pad={width}:{height}:(ow-iw)/2:{t}:color=0x19191b,setsar=1'

def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--top',type=int,default=TOP);p.add_argument('--bottom',type=int,default=BOTTOM);a=p.parse_args()
 if a.source.resolve()==a.output.resolve():raise ValueError('Use a new output path; prevent repeated padding')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 if a.source.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:image(Image.open(a.source),a.top,a.bottom).save(a.output)
 else:
  import imageio_ffmpeg
  ff=imageio_ffmpeg.get_ffmpeg_exe();subprocess.run([ff,'-y','-v','error','-i',str(a.source),'-vf',video_filter(top=a.top,bottom=a.bottom),'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset','fast','-crf','13','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(a.output)],check=True)
  subprocess.run([ff,'-v','error','-i',str(a.output),'-f','null','-'],check=True)
 a.output.with_suffix('.safe-area.json').write_text(json.dumps({'top_at_1080':a.top,'bottom_at_1080':a.bottom,'background':'#19191b','content_scaled_uniformly':True,'no_crop':True},indent=2));print(a.output)
if __name__=='__main__':main()
