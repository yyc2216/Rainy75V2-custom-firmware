# coding: utf-8
"""Reproducible single-bank V95 -> V98 time-only overlay. No hardware I/O."""
from pathlib import Path
import struct, hashlib, json, sys
R=Path(__file__).resolve().parent
BASE=0x08004000; END=0x08080000
sys.path.insert(0,str(R.parents[2]/"reverse_tools"))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
S=R.parent/"V95_lcd_layout/reports/V95_SINGLE_BANK.bin"
old=S.read_bytes()
assert len(old)==507804 and hashlib.sha256(old).hexdigest()=="f45de0a16b2964c977a81c2772949c490bd62567344b605e5d1bfc3bdbdf07cb"
assert old[0x807fc34-BASE:0x807fccc-BASE]==bytes([255])*152
A=bytearray(old+bytes([255])*(END-BASE-len(old)))
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB);cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
slots={".epoch":(0x804828c,0x80482d0),".prep":(0x80482d0,0x80482ea),".query":(0x807fb8c,0x807fbb2),".reply":(0x807fbd4,0x807fbec),".decode_tail":(0x807fbec,0x807fc04),".set":(0x807fc34,0x807fcac),".prep_rest":(0x807fcac,0x807fccc),".read":(0x807ff9c,0x807ffe0),".decode":(0x807ffe0,END)}
changes=[]
def patch(a,b,tag):
 assert BASE<=a<a+len(b)<=END
 assert all(a+len(b)<=x or y<=a for x,y,_ in changes)
 A[a-BASE:a-BASE+len(b)]=b;changes.append((a,a+len(b),tag))
def branch(a,target):
 b=bytes(ks.asm(f"bl 0x{target:x}",addr=a)[0]);ds=list(cs.disasm(b,a))
 assert len(b)==4 and ds[0].mnemonic=="bl" and ds[0].op_str==f"#0x{target:x}",ds
 return b
e=(R/"reports/rtc.elf").read_bytes();h=struct.unpack_from("<16sHHIIIIIHHHHHH",e)
secs=[struct.unpack_from("<10I",e,h[6]+i*h[11]) for i in range(h[12])]
st=secs[h[13]];names=e[st[4]:st[4]+st[5]]
seen=set()
for s in secs:
 if not s[2]&2 or not s[5]:continue
 n=names[s[0]:].split(b"\0",1)[0].decode()
 assert n in slots,n
 a,z=slots[n];assert s[3]==a and a+s[5]<=z,(n,s)
 patch(a,e[s[4]:s[4]+s[5]],n);seen.add(n)
assert seen==set(slots)
assert old[0x807fb12-BASE:0x807fb16-BASE].hex()=="01202861"
assert old[0x807fb6a-BASE:0x807fb70-BASE].hex()=="6860baf7a5fb"
assert old[0x807fbd2-BASE:0x807fbd4-BASE].hex()=="be20"
patch(0x807fb12,branch(0x807fb12,0x80482d0),"probe_stage_preserved_start_lick".replace(" ",""))
patch(0x807fb6a,branch(0x807fb6a,0x807fc34)+b"\x00\xbf","commit_stage_preserved")
patch(0x807fbd2,b"\x00\xbf","reply_entry")
# Verify all other existing bytes are bit-for-bit V95, including vectors, mode & game.
allowed={i for a,z,_ in changes for i in range(a-BASE,z-BASE)}
assert all(i in allowed for i,(x,y) in enumerate(zip(A,old)) if x!=y)
assert A[:256]==old[:256] and len(A)==END-BASE
prev=(R.parent/"V97_ertc_diag/reports/V97_RTC_TRIAL_SINGLE_BANK.bin").read_bytes()
assert hashlib.sha256(prev).hexdigest()=="28ebff8500de908badadcb838c2f085d3cc64d2641b59dcff334a79c818427a4"
assert all(any(x<=BASE+i<y for x,y in ((0x807fc34,0x807fccc),(0x807ff9c,0x807ffe0))) for i,(a,b) in enumerate(zip(A,prev)) if a!=b)
ds=list(cs.disasm(bytes(A[0x807fb8c-BASE:0x807fbb2-BASE]),0x807fb8c))
assert {i.address:i.op_str for i in ds if i.mnemonic in ("bl","b","beq","cbz")}=={0x807fb90:"#0x807fba6",0x807fb94:"#0x807fbac",0x807fb96:"#0x803a2ba",0x807fb9e:"#0x80482a4",0x807fba2:"r0, #0x807fbc2",0x807fba4:"#0x807fbb2",0x807fba6:"#0x807ff9c",0x807fbaa:"#0x807fbb2"}
assert A[0x807fc9c-BASE:0x807fca0-BASE]==struct.pack("<I",0x40023870)
digest=hashlib.sha256(A).hexdigest()
out=R/"reports/V98_RTC_TRIAL_SINGLE_BANK.bin";out.write_bytes(A)
report=dict(status="OFFLINE_CANDIDATE_NOT_FLASHED",sha256=digest,base_sha256=hashlib.sha256(old).hexdigest(),size=len(A),regions=[(hex(a),hex(z),n)for a,z,n in changes],rtc_only_diagnostic="LIST FB/FC lo=A5 (zero if invalid), lo=A6 (raw CRM BPDC)",backup_source="LICK internal RC, nominal 40000 Hz, divider 125*320; physical retention not established",retained_interval_max_seconds=86400,physical_validation=False)
(R/"reports/V98_build.json").write_text(json.dumps(report,indent=2),"utf8")
print("BUILD98",digest,len(A),flush=True)
