#!/usr/bin/env python3
"""Suggest a sustained song entrance, excluding sparse/quiet intro sounds.

uv run workflows/music-onset.py track.mp3 [--source-in seconds] [--json]
uv run workflows/music-onset.py track.mp3 --write-plan projects/<job> [--bed-db -20] [--source-in seconds]
The default stdout is the source in-point, including 16 ms attack pre-roll.
--write-plan saves the reviewed bed as <job>/hf-graphics/music-plan.json ({track, bed_db, source_in, tail}: the
keys lanes/premiere/place-music.py persists), which the lanes that do not lay the bed live read (Final Cut's
replay.py lays it from there).
This is an audio-envelope candidate: review the entrance, and use --source-in
for a deliberate quiet intro or another musical start. It does not detect beats.
"""
import argparse
import array
import json
import math
import subprocess
import sys
from pathlib import Path

RATE = 16000
BLOCK = 320  # 20 ms
PRE_ROLL = .016
BED_DB = -20     # the house flat bed in whole dB (background-music; place-music.py's BED_DB and --bed-db type)
TAIL = 2.0       # the tail fade-out, seconds (place-music.py's TAIL)


def sustained_entrance(powers):
    """First audible block followed by 1s at 90% occupancy near the main bed."""
    if len(powers) < 50:
        raise ValueError('Need at least one second of music; specify a source in-point.')
    window = sum(powers[:50])
    reference = window
    for i in range(50, len(powers)):
        window += powers[i] - powers[i-50]
        reference = max(reference, window)
    reference /= 50
    if reference <= 1e-10:
        raise ValueError('No audible music in the first 60s; specify a source in-point.')
    threshold = max(1e-6, reference * 10**(-18/10))
    active = [p >= threshold for p in powers]
    count = sum(active[:50])
    for i in range(len(active)-49):
        if i:
            count += active[i+49] - active[i-1]
        if active[i] and count >= 45:
            return {'entrance': round(i * BLOCK/RATE, 3),
                    'threshold_dbfs': round(10*math.log10(threshold), 2)}
    raise ValueError('No sustained entrance found; review the song and specify a source in-point.')


def analyze(track):
    result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(track),
                             '-t', '60', '-ac', '2', '-ar', str(RATE),
                             '-f', 's16le', '-'], capture_output=True, check=True)
    samples = array.array('h', result.stdout)
    if sys.byteorder != 'little':
        samples.byteswap()
    # Preserve energy in both channels; mono downmix could cancel out-of-phase music.
    powers = [sum(x*x for x in samples[i:i+BLOCK*2]) / (BLOCK*2*32768**2)
              for i in range(0, len(samples)-BLOCK*2+1, BLOCK*2)]
    found = sustained_entrance(powers)
    found['source_in'] = round(max(0, found['entrance']-PRE_ROLL), 6)
    found['method'] = 'sustained-envelope-candidate'
    return found


def write_plan(job, track, bed_db, source_in):
    """<job>/hf-graphics/music-plan.json, the reviewed bed every lane lays from. Returns its path."""
    plan = Path(job) / 'hf-graphics' / 'music-plan.json'
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps({'track': str(Path(track).resolve()), 'bed_db': bed_db, 'source_in': source_in,
                                'tail': TAIL}, indent=2) + '\n', encoding="utf-8")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('track')
    parser.add_argument('--source-in', type=float)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--write-plan', metavar='JOB', help='save the bed as JOB/hf-graphics/music-plan.json')
    # whole dB, place-music.py's own type: a float here (-20.0) crashed place-music on the shared plan (2026-10-13)
    parser.add_argument('--bed-db', type=int, default=BED_DB, help='the bed level in whole dB (default %(default)s)')
    args = parser.parse_args(argv)
    try:
        if args.write_plan and not Path(args.write_plan).is_dir():
            raise ValueError(f'--write-plan {args.write_plan}: no such job folder')
        if args.write_plan and not Path(args.track).is_file():
            raise ValueError(f'no such track: {args.track}')
        if not math.isfinite(args.bed_db):
            raise ValueError('bed-db must be a finite number')
        if args.source_in is None:
            result = analyze(args.track)
        else:
            if not math.isfinite(args.source_in) or args.source_in < 0:
                raise ValueError('source-in must be a finite nonnegative number')
            result = {'source_in': args.source_in, 'method': 'explicit'}
        if args.write_plan:
            plan = write_plan(args.write_plan, args.track, args.bed_db, result['source_in'])
            print(f"wrote {plan}: bed {args.bed_db:g} dB from {result['source_in']} s ({result['method']}), "
                  f"{TAIL:g} s tail")
        else:
            print(json.dumps(result) if args.json else result['source_in'])
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
