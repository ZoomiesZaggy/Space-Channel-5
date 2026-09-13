"""Separate game-frame spacing, execution and presentation in a host timing CSV."""
import argparse
import csv
import json


def analyze(rows):
    if not rows:
        raise ValueError('Empty host timing trace')
    frequency = int(rows[0]['frequency'])
    start = int(rows[0]['begin_qpc'])
    frames = []
    previous = None
    run = present = 0
    for row in rows:
        begin, middle, end = (int(row[key]) for key in ('begin_qpc', 'run_end_qpc', 'end_qpc'))
        if not begin <= middle <= end or int(row['frequency']) != frequency or frequency <= 0:
            raise ValueError('Invalid timing row')
        run += middle - begin
        present += end - middle
        if int(row['frames']):
            if previous is not None:
                elapsed = end - int(previous['end_qpc'])
                frames.append(dict(
                    wall_seconds=(end-start)/frequency,
                    interval_ms=elapsed*1000/frequency,
                    device_interval_ms=(int(row['device_end'])-int(previous['device_end']))/200000,
                    run_ms=run*1000/frequency,
                    present_ms=present*1000/frequency,
                    between_chunks_ms=(elapsed-run-present)*1000/frequency,
                ))
            previous = row
            run = present = 0
    return dict(frame_intervals=len(frames), longest=sorted(frames, key=lambda x: x['interval_ms'], reverse=True)[:10])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv')
    args = parser.parse_args()
    with open(args.csv, newline='') as source:
        print(json.dumps(analyze(list(csv.DictReader(source))), indent=2))
