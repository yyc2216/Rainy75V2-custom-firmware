.syntax unified
.thumb
.section .entry.veneer,"ax",%progbits
.global compact_life
.type compact_life,%function
.thumb_func
compact_life:
 b.w v86_lifecycle
.global compact_key
.type compact_key,%function
.thumb_func
compact_key:
 b.w v86_key
.global compact_smoke
.type compact_smoke,%function
.thumb_func
compact_smoke:
 b.w v86_smoke
