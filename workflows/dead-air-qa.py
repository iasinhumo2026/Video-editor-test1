#!/usr/bin/env python3
"""Read-only dialogue dead-air gate, independent of music and no_refine pins.
Usage: uv run workflows/dead-air-qa.py projects/JOB [--cuts PATH] [--json PATH]
Flags >=0.65s quiet runs using 10ms RMS and a speech-relative threshold.
Bridges isolated <40ms noise spikes; never changes cuts automatically.
Each run also says where speech resumes (resume / resume_source): a soft onset under 40 ms ("it's") is bridged
as a spike, so the run's end can sit in the NEXT word's vowel, and a split IN taken from it cut the onset away
(3 of 8 splits on a real take, 2026-10-13). A bridged burst that reaches the run's end through less than a stop
closure of quiet (RESUME_GAP) is that onset.
A segment carrying "media" (laid from a substitute file, e.g. a lip-sync re-record) is not the
raw's audio: it is skipped with a printed line, still counts its duration on the timeline, and
no quiet run is joined across it.
"""
import argparse,array,json,math,subprocess,sys
from pathlib import Path
HOP=.01
RESUME_GAP=.15

def quiet_mask(values,floor):
    peak=max(values)
    threshold=max(peak-28,min(floor+14,peak-18))
    mask=[v<threshold for v in values];i=0
    while i<len(mask):
        if mask[i]:i+=1;continue
        j=i
        while j<len(mask) and not mask[j]:j+=1
        if i>0 and j<len(mask) and j-i<4:mask[i:j]=[True]*(j-i)
        i=j
    return mask,threshold

def quiet_runs(mask):
    i=0
    while i<len(mask):
        if not mask[i]:i+=1;continue
        j=i
        while j<len(mask) and mask[j]:j+=1
        if (j-i)*HOP>=.65:yield i,j
        i=j

def resumes(raw,i,j):
    """The frame where speech comes back in the bridged run [i, j) of the UNBRIDGED quiet flags `raw`: the start of
    the earliest burst that reaches j through quiet gaps each shorter than RESUME_GAP; j when there is none."""
    r=j;k=j-1
    while k>=i:
        q=k
        while q>=i and raw[q]:q-=1
        if q<i or (r-1-q)*HOP>=RESUME_GAP:break
        b=q
        while b-1>=i and not raw[b-1]:b-=1
        r=b;k=b-1
    return r

def levels(pcm,hop=160):
    """10 ms RMS in dBFS over s16 samples, and the file's floor (its 10th percentile)."""
    envelope=[20*math.log10(math.sqrt(sum(x*x for x in pcm[i:i+hop])/len(pcm[i:i+hop]))/32768+1e-9) for i in range(0,len(pcm),hop)]
    return envelope,sorted(envelope)[len(envelope)//10]

def scan(cuts,level,say=print):
    """The quiet runs of the EDL's timeline. level(cut) -> (envelope, floor) of its raw clip.
    Returns (findings, timeline duration, segments not audited)."""
    findings=[];timeline=0;skipped=[];mask=[];raw=[];times=[]
    def flush():
        for i,j in quiet_runs(mask):
            t,seg,source,thr=times[i];end=times[j-1][0]+HOP;r=resumes(raw,i,j)
            at,rseg,rsrc,_=times[r] if r<j else (end,times[j-1][1],times[j-1][2]+HOP,0)
            findings.append(dict(start=round(t,3),end=round(end,3),duration=round(end-t,3),segment=seg,end_segment=times[j-1][1],source_start=round(source,3),threshold_db=round(thr,1),resume=round(at,3),resume_segment=rseg,resume_source=round(rsrc,3)))
        mask.clear();raw.clear();times.clear()
    for index,c in enumerate(cuts):
        if c.get('media'):
            # its audio is the substitute file's, not the raw's: nothing to measure here, and a run
            # either side of it must not be joined across it
            flush();skipped.append(dict(segment=index,media=c['media']))
            say(f"seg{index:02d} laid from {c['media']}: not audited on the raw")
        else:
            envelope,floor=level(c)
            a=round(c['start']/HOP);b=round(c['end']/HOP);values=envelope[a:b]
            if len(values):
                m,threshold=quiet_mask(values,floor)
                mask.extend(m);raw.extend(v<threshold for v in values);times.extend((timeline+k*HOP,index,c['start']+k*HOP,threshold) for k in range(len(m)))
        timeline+=c['end']-c['start']
    flush()
    return findings,timeline,skipped

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('job',type=Path);ap.add_argument('--cuts',type=Path);ap.add_argument('--json',type=Path);args=ap.parse_args()
    cuts=json.loads((args.cuts or args.job/'transcript/cuts.json').read_text(encoding="utf-8"))['segments'];cache={}
    def level(c):
        path=args.job/'raw'/Path(c['clip']).name
        if path not in cache:
            r=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','16000','-f','s16le','-'],capture_output=True,check=True)
            cache[path]=levels(array.array('h',r.stdout))
        return cache[path]
    findings,timeline,skipped=scan(cuts,level,say=lambda m:print(m,file=sys.stderr))
    report={'duration':timeline,'segments':len(cuts),'dead_air':findings,'passed':not findings}
    if skipped:report['not_audited']=skipped
    if args.json:args.json.write_text(json.dumps(report,indent=2)+'\n', encoding="utf-8")
    print(json.dumps(report,indent=2));return bool(findings)
if __name__=='__main__':raise SystemExit(main())
