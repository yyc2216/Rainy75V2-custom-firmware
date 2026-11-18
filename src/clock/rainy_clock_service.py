# -*- coding: utf-8 -*-
"""Rainy75V2 USB clock monitor; reuses verified V39/V31 transport; never flashes.
Run under one interactive-user scheduled task. --self-test is hardware-free.
"""
import argparse, datetime as dt, json, runpy, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
legacy = runpy.run_path(str(HERE / "V39_USB连接自动校时_待启用.py"))
Device, clock_seconds, TZ = (legacy[k] for k in ("Device","clock_seconds","TZ"))
fingerprint, once = legacy["fingerprint"], legacy["once"]
LOG = HERE / "rainy_clock_service.jsonl"
DIAG = HERE / "V98_pre_sync_diagnostic.json"
POLL, HEALTH, RESYNC = 3, 30, 24*3600
def log(event, **data):
    item = {"at":dt.datetime.now(TZ).isoformat(timespec="seconds"),"event":event,**data}
    # Limit local diagnostics to 2 MiB plus one rotated log.
    if LOG.exists() and LOG.stat().st_size > 2*1024*1024:
        LOG.replace(LOG.with_suffix(".previous.jsonl"))
    with LOG.open("a",encoding="utf8") as f:
        f.write(json.dumps(item,ensure_ascii=False)+"\n")
    print(json.dumps(item,ensure_ascii=True),flush=True)

class Monitor:
    def __init__(self, fingerprint, sync, query, now_pc, emit, before_connect_sync=None):
        self.fingerprint,self.sync,self.query,self.now_pc,self.emit = fingerprint,sync,query,now_pc,emit
        self.path=None; self.last_sync=None; self.next_try=0; self.next_health=0; self.failures=0
        self.before_connect_sync=before_connect_sync;self.pending_connect_sample=False
    def tick(self, now):
        path=self.fingerprint()
        if path!=self.path:
            self.emit("USB_CONNECTED" if path else "USB_DISCONNECTED")
            self.path=path;self.last_sync=None;self.next_try=now;self.next_health=now;self.failures=0
            self.pending_connect_sample=bool(path)
        if not path: return
        if now<self.next_try: return
        need = self.last_sync is None or now-self.last_sync>=RESYNC
        if not need and now>=self.next_health:
            self.next_health=now+HEALTH
            try:
                board=self.query()
                need=abs(board-self.now_pc())>30
                if need:self.emit("CLOCK_DRIFT",device=board,computer=self.now_pc())
            except Exception as e:
                need=True
                self.emit("CLOCK_QUERY_FAILED",error=str(e))
        if not need:return
        if self.pending_connect_sample:
            self.pending_connect_sample=False
            if self.before_connect_sync:
                try:self.before_connect_sync()
                except Exception as e:self.emit("PRE_SYNC_DIAG_ERROR",error=repr(e))
        try:
            result=self.sync()
            self.last_sync=now;self.next_health=now+HEALTH;self.next_try=now;self.failures=0
            self.emit("SYNC_SUCCESS",data=result)
        except Exception as e:
            self.last_sync=None
            self.failures+=1
            # Every attempt re-probes supported firmware before any write.
            delay=min(30,3*2**min(self.failures-1,4))
            self.next_try=now+delay
            self.emit("SYNC_RETRY",attempt=self.failures,retry_seconds=delay,error=str(e))
def query():
    with Device() as dev:return dev.query()
def capture_retention():
    """Read-only V98 diagnostic, explicitly armed and limited to USB attach.
    No probe until snapshot: probe starts LICK, sync overwrites backup domain.
    Following USB attach may itself reset the board; this cannot establish
    the state during an earlier disconnected interval.
    """
    if not DIAG.exists():return
    arming=json.loads(DIAG.read_text("utf8"))
    if arming.get("expected_firmware")!="V98" or arming.get("remaining",0)<=0:return
    if clock_seconds()>arming["expires_epoch"]:
        DIAG.unlink(missing_ok=True);return
    class ReadDevice(Device):
        def ack(self):
            g=Device.ack.__globals__;last=None
            for _ in range(4):
                self.send(g["ack_packet"]())
                raw=self.dev.read(256,1000)
                try:
                    if not raw:raise TimeoutError("empty ACK")
                    return g["parse_ack"](raw)
                except (AssertionError,TimeoutError) as e:
                    last=e;time.sleep(.04)
            raise RuntimeError("No validated pre-sync ACK") from last
    data={"expected_firmware":"V98","pc_epoch_before":clock_seconds(),"read_only":True}
    try:
        with ReadDevice() as dev:
            for name,sel in (("backup_control",0xa6),("rtc_epoch",0xa5),("normal_epoch",0)):
                try:
                    a=dev.list(251,sel,0);b=dev.list(252,sel,0)
                    data[name]={"low":a,"high":b,"value":(a["value"]|(b["value"]<<16)) if a["status"]==b["status"]==0 else None}
                except Exception as e:data[name]={"error":repr(e)}
    finally:
        data["pc_epoch_after"]=clock_seconds()
        log("PRE_SYNC_RETENTION",data=data)
        arming["remaining"]-=1
        if arming["remaining"]<=0:DIAG.unlink(missing_ok=True)
        else:DIAG.write_text(json.dumps(arming),"utf8")
def selftest():
    state={"path":None,"fail":True,"drift":False,"count":0,"query_fail":False}
    events=[];order=[]
    def sync():
        order.append("sync")
        state["count"]+=1
        if state["fail"]:raise TimeoutError("transient")
        return {"ok":True}
    def read():
        if state["query_fail"]:raise RuntimeError("clock reset")
        return 900 if state["drift"] else 1000
    m=Monitor(lambda:state["path"],sync,read,lambda:1000,lambda event,**kw:events.append(event),lambda:order.append("pre"))
    m.tick(0);assert state["count"]==0
    state["path"]="A";m.tick(1);assert state["count"]==1
    m.tick(2);assert state["count"]==1
    state["fail"]=False;m.tick(4);assert state["count"]==2 and m.last_sync==4
    m.tick(5);assert state["count"]==2
    m.tick(34);assert state["count"]==2
    state["drift"]=True;m.tick(64);assert state["count"]==3
    state["drift"]=False;state["query_fail"]=True;m.tick(94);assert state["count"]==4
    state["query_fail"]=False;state["path"]=None;m.tick(95);assert m.last_sync is None
    state["path"]="A";m.tick(96);assert state["count"]==5
    m.tick(96+RESYNC);assert state["count"]==6
    assert events.count("USB_CONNECTED")==2 and events.count("SYNC_RETRY")==1
    assert order==["pre","sync","sync","sync","sync","pre","sync","sync"],order
    print("SELF_TEST_PASS: connect, transient retry, no redundant sync, drift, reset, disconnect/reconnect, periodic")
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--self-test",action="store_true");args=parser.parse_args()
    if args.self_test:return selftest()
    import msvcrt
    lock=(HERE/"rainy_clock_service.lock").open("a+b")
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        lock.close();print("ALREADY_RUNNING",flush=True);return
    try:
        log("MONITOR_STARTED",poll_seconds=POLL,health_seconds=HEALTH)
        m=Monitor(fingerprint,once,query,clock_seconds,log,capture_retention)
        while True:
            try: m.tick(time.monotonic())
            except Exception as e: log("MONITOR_ERROR",error=str(e))
            time.sleep(POLL)
    finally:
        lock.close()
if __name__=="__main__":main()
