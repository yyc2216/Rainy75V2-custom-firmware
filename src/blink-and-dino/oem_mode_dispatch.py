# coding: utf-8
"""Native selector owns the game root; one common OEM tick handles refresh.
No changes to fade, backlight, LVGL or LCD driver. Offline candidate."""
from pathlib import Path
import hashlib,sys,json,re,struct
R=Path(__file__).resolve().parent;P=R.parent;PR=P.parents[1]
s=(R/"V61_build_transition.py").read_text("utf8")
exec(s[:s.index('res={"V29":')])
B=(R/"reports"/"V62_temp_diagnostic_OFFLINE.bin").read_bytes()
assert sha(B)=="41b0f41a1acf7a95d2c1efa587c300f230bbc596b854759af4f1c4277c6820ef"
A=bytearray(B); patches=[]
def patch(at,expected,new,tag):
 off=at-BASE
 assert bytes(A[off:off+len(expected)])==expected,(tag,hex(at))
 assert len(new)==len(expected)
 A[off:off+len(new)]=new
 patches.append(dict(address=hex(at),before=expected.hex(),after=new.hex(),tag=tag))
def extend(at,code,tag):
 assert at>=BASE+len(A) and at+len(code)<=END
 A.extend(b"\xff"*(at-BASE-len(A))+code)
 print(tag,hex(at),len(code),flush=True)
# existing game preparation/update code without display ownership or refresh.
# Accept selected mode explicitly in r0, not native active index.
# r7 retains requested mode on the non-game path. No LVGL task handler here.
new=tick_src.replace("ldr r4,=0x2003eda0\nldrb r0,[r4,#0x12]\nmov r7,r0","mov r7,r0").replace("bl 0x802dca8\n","",1)
new=new.replace("bl 0x8019f68\ntick_exit:","tick_exit:")
# Stock status decoder checks active mode, so defer return refresh to normal
# dispatcher AFTER the native selector updates MODE+0x12. Preserve the flag.
new=new.replace("cmp r7,#0\nbne delegate_v18_no_state\nldr r0,[r6,#108]","cmp r7,#0\nbne delegate_v18_no_state\nldr r0,=0x2003eda0\nldrb r0,[r0,#0x12]\ncbnz r0,delegate_v18_no_state\nldr r0,[r6,#108]")
# Existing root preparation helper (V61) only creates objects, never loads.
addr=0x801ad34;end=0x801ae68
raw=asm(addr,new)
if len(raw)>end-addr:raise AssertionError(("update code budget",len(raw),end-addr))
audit(addr,new,raw)
patch(addr,B[addr-BASE:end-BASE],raw+b"\xff"*(end-addr-len(raw)),"update_pixels_only_explicit_target")
# Wrapper for original 5ms loop. One OEM path for all modes, including dino:
# custom update first, then original scene tick (calls original LVGL scheduler).
dispatcher=(BASE+len(A)+3)&~3
source=f"""
push {{r4,lr}}
ldr r4,=0x2003eda0
ldrb r0,[r4,#0x12]
bl 0x{addr:x}
pop.w {{r4,lr}}
b.w 0x8019f68
"""
raw=asm(dispatcher,source);audit(dispatcher,source,raw);extend(dispatcher,raw,"COMMON_DISPATCH")
site=0x807a73e
assert next(CS.disasm(B[site-BASE:site-BASE+4],site)).op_str=="#0x801ad34"
patch(site,B[site-BASE:site-BASE+4],asm(site,f"bl 0x{dispatcher:x}"),"one_common_original_refresh_tick")
# The native type0 selector resolves its root immediately before its existing
# (unchanged) BL lv_scr_load at 0x805ac56. Provide the selected root, no load
# or refresh call in the provider. Prepare blink pixels before returning.
# r5= native requested mode, r6= native mode state (callee-saved).
provider=(BASE+len(A)+3)&~3
source=f"""
push {{r4,lr}}
cmp r5,#2
beq prepare
cmp r5,#0
bne fallback
prepare:
mov r0,r5
bl 0x{addr:x}
cmp r5,#2
bne fallback
bl 0x8019cf0
cbz r0,game_failed
movw r1,#0x3c68
ldr r2,[r0,r1]
cmp r2,#0
beq game_failed
movw r1,#0x3c6c
ldr r0,[r0,r1]
cbz r0,game_failed
mov r0,r2
pop {{r4,pc}}
game_failed:
# r5 is the caller's selected mode, committed by the original selector.
# Fall back to mode0 if preparation failed, rather than claim mode2 active.
movs r5,#0
mov r0,r5
bl 0x801ad34
fallback:
ldr r0,=0x2004c9bc
ldr r0,[r0,#8]
pop {{r4,pc}}
"""
raw=asm(provider,source);audit(provider,source,raw);extend(provider,raw,"NATIVE_ROOT_PROVIDER")
# Verify original pointer load resolves same global blink root address.
site=0x805ac50
ins=list(CS.disasm(B[site-BASE:site-BASE+10],site))
assert ins[0].mnemonic=="ldr.w" and ins[1].mnemonic=="ldr" and ins[2].op_str=="#0x802b0e0",[(i.mnemonic,i.op_str) for i in ins]
lit=(site+4)&~3
ptr=struct.unpack_from("<I",B,lit+0x708-BASE)[0]
assert struct.unpack_from("<I",B,lit+0x708-BASE)[0]==0x2004c9c4,hex(ptr)
patch(site,B[site-BASE:site-BASE+6],asm(site,f"bl 0x{provider:x}\nnop"),"native_select_root_only")
# Existing V61 game-root activation helper unreachable. Erase only its known 32B.
lo=0x807fc34;hi=0x807fc54
assert len(B[lo-BASE:hi-BASE])==32
patch(lo,B[lo-BASE:hi-BASE],b"\xff"*32,"remove_private_screen_reclaim_helper")
o=(PR/"回滚备份_20261113"/"原厂固件_按发行日期"/"20261109-2"/"ips.bin").read_bytes()
assert sha(o)=="32defab7902e57eb972a577fc6cbf3a7e57bc772d59b99f11038370412b77f41"
for x,y in ((0x805a68c,0x805a70a),(0x805ac56,0x805ac72),(0x805acac,0x805ae0a),(0x805b030,0x805b0d8),(0x805b244,0x805b2dc),(0x802dca8,0x802de48),(0x8033664,0x8033696),(0x805d684,0x805d7bc)):
 assert A[x-BASE:y-BASE]==o[x-BASE:y-BASE]
allowed=set()
for q in patches:
 x=int(q["address"],16)-BASE;allowed.update(range(x,x+len(bytes.fromhex(q["before"]))))
assert all(i in allowed for i,(a,b) in enumerate(zip(A,B)) if a!=b)
m=dict(status="OFFLINE",sha256=sha(A),base_sha256=sha(B),bytes=len(A),dispatcher=hex(dispatcher),provider=hex(provider),update=hex(addr),patches=patches,common_oem_fade_and_transfer_unchanged=True)
(R/"reports"/"V69_oem_owned_game_OFFLINE.bin").write_bytes(A)
(R/"reports"/"V69_manifest.json").write_text(json.dumps(m,indent=2),"utf8")
print("V69_BUILD_PASS",m["sha256"],len(A),flush=True)
