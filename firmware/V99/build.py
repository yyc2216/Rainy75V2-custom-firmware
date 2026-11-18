from pathlib import Path
import hashlib,json,sys,argparse
R=Path(__file__).resolve().parent;B=0x08004000

from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
ap=argparse.ArgumentParser(description="Offline V98-to-V99 firmware builder; no USB I/O")
ap.add_argument("base", type=Path, help="Legally obtained exact V98 baseline image")
ap.add_argument("output", type=Path, help="New V99 output image")
args=ap.parse_args()
assert args.base.resolve()!=args.output.resolve() and not args.output.exists(), "Output must be new"
base=args.base.read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(base)=="c57612eeaf390c6822866debe1652af6401e9094ec9dd1448006e47d9ce07138"
A=bytearray(base)
addr=0x0804807c
assert A[addr-B:addr-B+2]==bytes.fromhex("2f21")
A[addr-B:addr-B+2]=bytes.fromhex("5e21")
# Within the original side-only branch: sweep the thin face across
# the depth interval instead of rendering two separated ellipses.
start=0x08048138;end=0x0804815e
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
asm="""ldr r0,[sp,#0x14]
add r0,r11
eors.w r1,r0,r11
it mi
movmi r0,#0
lsls r0,r0,#4
.byte 0x90,0xfb,0xf5,0xf2
adds r2,#16
ldr r0,[sp,#0x7c]
mov r1,r10
bl 0x080481ce
mov r7,r0
cbz r0,0x0804819e
movs r0,#3
mov r4,r8
mov r9,r11"""
patch=bytearray(ks.asm(asm,addr=start)[0])
# Keystone's mixed .byte+assembly internal PC can drift by four bytes.
# Reassemble each PC-relative instruction at its actual address.
for pc,ins,n in ((0x8048150,"bl 0x080481ce",4),(0x8048156,"cbz r0,0x0804819e",2)):
 q=bytes(ks.asm(ins,addr=pc)[0]);assert len(q)==n
 patch[pc-start:pc-start+n]=q
c=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
branches={i.address:i.op_str for i in c.disasm(bytes(patch),start) if i.mnemonic in ("bl","cbz","b")}
assert branches=={0x8048150:"#0x80481ce",0x8048156:"r0, #0x804819e"},branches
assert len(patch)==end-start,(len(patch),end-start,patch.hex())
A[start-B:end-B]=patch
# The face math stays byte-identical; only routing changes, reclaiming its redundant
# base-light reload. Advance common lighting by one halfword and fix its BL.
def write_ins(pc,ins,n):
 q=bytes(ks.asm(ins,addr=pc)[0]);assert len(q)==n,(pc,ins,q.hex())
 A[pc-B:pc-B+n]=q
write_ins(0x8048132,"ldr r0,[sp,#0x20]",2)
write_ins(0x8048134,"bls 0x08048186",2)
write_ins(0x8048136,"b 0x0804815e",2)
A[0x804815e-B:0x8048184-B]=base[0x804815c-B:0x8048182-B]
write_ins(0x8048180,"bl 0x0804789a",4)
write_ins(0x8048184,"nop",2)
routing={i.address:i.op_str for i in c.disasm(bytes(A[0x8048132-B:0x8048186-B]),0x8048132) if i.mnemonic in ("bl","cbz","b","bls")}
assert routing=={0x8048134:"#0x8048186",0x8048136:"#0x804815e",0x8048150:"#0x80481ce",0x8048156:"r0, #0x804819e",0x8048180:"#0x804789a"},routing
assert all(i+B==addr or 0x8048132<=i+B<0x8048186 for i,(a,b) in enumerate(zip(base,A)) if a!=b)
changed=sum(a!=b for a,b in zip(base,A))
c=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
assert next(c.disasm(bytes(A[addr-B:addr-B+2]),addr)).op_str=="r1, #0x5e"
assert sha(A)=="2b7737a840947ea87494ea91bb41a95dd02629a520a21c81fbd0d93456f92065"
args.output.write_bytes(A)
report=dict(status="BUILT_NOT_FLASHED",base_sha256=sha(base),sha256=sha(A),size=len(A),changed_bytes=changed,side_sweep=True,original_lighting_preserved=True,thickness_old=47,thickness_new=94,unchanged_clock=True)

print(report,flush=True)
