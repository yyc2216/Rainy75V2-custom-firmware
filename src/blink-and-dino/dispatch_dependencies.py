# coding: utf-8
"""Offline: fix first dino frame. Preserve stock screen loading, but draw before
selecting custom game root and calling LVGL scheduler. Applies to V29 and V59."""
from pathlib import Path
import sys,struct,json,hashlib,re
R=Path(__file__).resolve().parent;P=R.parent
sys.path.insert(0,str(P.parents[1]/"reverse_tools"))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
KS=Ks(KS_ARCH_ARM,KS_MODE_THUMB);CS=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
BASE=0x08004000; END=0x08080000
sha=lambda b:hashlib.sha256(b).hexdigest()
V29=P/"V29_immediate_oem_status_on_return"
v29=V29/"V29_第三模式_候选固件_仅离线禁止刷写.bin"
v59=P/"V59_integrated_maintenance"/"reports"
old=v29.read_bytes(); assert sha(old)=="117b4192d617b142937fc6af54cf592a6f76a35f0a3b38b2e441c3fe9f4bfef2"
m59=json.loads((v59/"V59_manifest.json").read_text("utf8"))
a59=(v59/"V59_first_OFFLINE_NEVER_FLASH.bin").read_bytes()
b59=(v59/"V59_second_OFFLINE_NEVER_FLASH.bin").read_bytes()
assert sha(a59)==m59["firstbank_sha256"] and sha(b59)==m59["secondbank_sha256"]
source=(V29/"V29_原厂图标和纯净恐龙界面_离线构建.py").read_text("utf8")
tick_match=re.search(r'tick=add_code\([^,]+,(f"""[\s\S]*?""")\)',source)
assert tick_match
env={"S":0x3c10,"LAST_VISIBLE_MODE":104,"REFRESH_ON_RETURN":108,"MAGIC":0x44494e4f,"HI":12,"ACTIVE":76,"GAME_ROOT":88,"GAME_IMAGE":92,"PHASE":4,"LAST":40,"RNG":44,"FRAME":68,"ensure_active_root":0x801acc0,"reset":0x801a960,"icon_toggle":0x801ac94,"spawn":0x801a890,"step":0x801aa1c,"render":0x801ab88}
tick_src=eval(tick_match.group(1),env)
def asm(at,s):
 return bytes(KS.asm(s,addr=at)[0])
def audit(at,s,b):
 lines=[];labels={}
 for l in s.splitlines():
  l=l.strip()
  if not l or l.startswith("#"):continue
  if l.endswith(":"):labels[l[:-1]]=len(lines)
  else:lines.append(l)
 d=list(CS.disasm(b,at))
 assert len(d)>=len(lines)
 for i,l in enumerate(lines):
  op=l.split()[0]
  if op not in ("b","b.w","bl","beq","bne","bne.w","beq.w","cbz","cbnz","blo","bls"):continue
  t=l.split(",")[-1].strip() if op in ("cbz","cbnz") else l.split()[-1]
  expected=d[labels[t]].address if t in labels else int(t,16)
  assert int(d[i].op_str.rsplit("#",1)[-1],16)==expected,(l,d[i])
def build(data,mode,tag):
 addr=0x801ad34;end=0x801ae68
 original=tick_src.replace("cmp r7,#2",f"cmp r7,#{mode}")
 assert asm(addr,original)==data[addr-BASE:end-BASE],("original routine mismatch",tag,len(asm(addr,original)))
 # Use a separate activation helper (32 bytes max). Source image is already
 # rendered; screen ownership is reclaimed even when physics does not advance.
 helper=(BASE+len(data)+3)&~3
 # On a missing LVGL display, retain original task behavior.
 hsrc="""
push {r4,lr}
ldr r4,[r0,#88]
cbz r4,done
bl 0x802a7f0
cbz r0,done
ldr r1,[r0,#0x10]
cmp r1,r4
beq done
mov r0,r4
bl 0x802b0e0
done:
pop.w {r4,lr}
b.w 0x802dca8
"""
 h=asm(helper,hsrc);audit(helper,hsrc,h)
 assert helper+len(h)<=END,(tag,len(h),END-helper)
 new=original.replace("bl 0x802dca8\n","",1)
 new=new.replace("blo tick_exit","blo game_tick_exit").replace("cbz r0,tick_exit","cbz r0,game_tick_exit")
 new=new.replace("b tick_exit\nnot_dino_screen:",f"game_tick_exit:\nmov r0,r6\nbl 0x{helper:x}\nb tick_exit\nnot_dino_screen:")
 # Preserve exactly the existing 308-byte routine budget. Shorten equivalent
 # no-flags compare w/ immediate-zero to CBZ if target within encoding range.
 # First try direct assembly, then remove redundant compare/branch.
 raw=asm(addr,new)
 if len(raw)>end-addr:
  new=new.replace("cmp r5,#0\nbeq.w delegate_v18_no_state","cmp r5,#0\nbeq delegate_v18_no_state")
  raw=asm(addr,new)
 assert len(raw)<=end-addr,(tag,len(raw),end-addr)
 audit(addr,new,raw)
 A=bytearray(data)
 A[addr-BASE:end-BASE]=raw+b'\xff'*(end-addr-len(raw))
 # Existing helper creates root/image only; no early lv_scr_load.
 at=0x801ad20
 assert next(CS.disasm(data[at-BASE:at-BASE+4],at)).op_str=="#0x802a7f0"
 A[at-BASE:at-BASE+2]=asm(at,"pop {r4,r5,r6,pc}")
 A+=b'\xff'*(helper-BASE-len(A))+h
 assert len(A)<=END-BASE
 allowed=set(range(addr-BASE,end-BASE))|set(range(at-BASE,at-BASE+2))
 assert all(i in allowed for i,(x,y) in enumerate(zip(A,data)) if x!=y)
 # Preserve original ROM/assets; explicit no unrelated modifications.
 assert A[:256]==data[:256] and A[0x801ae94-BASE:0x801b0e0-BASE]==data[0x801ae94-BASE:0x801b0e0-BASE]
 (R/"reports"/f"{tag}_OFFLINE_NEVER_FLASH.bin").write_bytes(A)
 result={"sha256":sha(A),"base_sha256":sha(data),"bytes":len(A),"firstbank_tail_free":END-BASE-len(A),"activation_helper":hex(helper),"helper_bytes":len(h),"tick_bytes":len(raw),"mode":mode,"physical_test":False}
 print(tag,result,flush=True)
 return result
res={"V29":build(old,2,"V61_V29"),"V59":build(a59,6,"V61_V59"),"bank2_unchanged":m59["secondbank_sha256"],"status":"OFFLINE_ONLY"}
(R/"reports"/"V61_transition_manifest.json").write_text(json.dumps(res,indent=2),"utf8")
