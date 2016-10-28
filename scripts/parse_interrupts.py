#!/usr/bin/python

'''
Input:  raw data from /proc/interrupts
Output: json timeseries file with total interrupts per cpu thread
'''

import sys
import os
import json
import re
from datetime import datetime

t0 = -1
def format_line(lines, prev_interrupts):
    global t0
    # Read timestamp
    t = datetime.strptime(lines[0], '%Y%m%d-%H%M%S')
    if t0 == -1: t0 = t
    t_sec = (t - t0).total_seconds()

    # Read number of cpus
    num_cpu = len(lines[1].split('CPU')) - 1
    interrupts = False

    # Parse raw interrupt count for each IRQ. Sum all together for each core
    for line in lines[2:]:
        regex_str = '\s*(\w+):' + num_cpu*'\s+(\d+)' + '\s+.*'
        m = re.match(regex_str, line)
        if m:
            # Raw interrupt count for this IRQ at this time
            vals = map(int, m.groups()[1:num_cpu + 1])
            if not interrupts:
                interrupts = vals
            else:
                # Sum interrupts generated on each core
                interrupts = [i + j for i, j in zip(vals, interrupts)]

    if prev_interrupts:
        data = ([i - j for i, j in zip(interrupts, prev_interrupts)])
        csv_line = '%g,%s\n' % (t_sec, ",".join([str(i) for i in data]))
        return (csv_line, interrupts)
    else:
        t0 = -1  # Reset once since we start on 2nd timestamp
        return ('', interrupts)

def csv_to_json(csv_str):
    '''
    Parses a csv string with format:
        t1,interrupts1a,interrupts2a,interrupts3a
        t2,interrupts1b,interrupts2b,interrupts3b
        t3,interrupts1c,interrupts2c,interrupts3c
    
    Returns object with 2 keys:
        "labels" as first column (time data)
        "datasets" as list of nested objects, one for each remaining column
    obj = {
        "labels": [t1, t2, t3],
        datasets = [
            {"label": cpu1, "data":[interrupts1a, interrupts1b, interrupts1c]},
            {"label": cpu2, "data":[interrupts2a, interrupts2b, interrupts2c]},
            {"label": cpu3, "data":[interrupts3a, interrupts3b, interrupts3c]}
            ]
        }
    '''
    lines = csv_str.strip().split('\n')
    field_names = lines[0].split(',')
    num_cols = len(lines[0].split(',')) - 1  # Subtract first column (time data)
    times = []
    # Create a list of lists of data
    datasets = [[int(i)] for i in lines[0].split(',')[1:]]
    for line in lines[1:]:
        fields = line.split(',')
        times.append(int(fields[0]))
        col = 0
        for field in fields[1:]:
            datasets[col].append(int(field))
            col += 1

    # Now construct json object
    cpu = 0
    all_datasets = []
    for dataset in datasets:
        all_datasets.append({"label": "cpu%g" % cpu,
                "data": dataset})
        cpu += 1
    obj = {"labels": times, "datasets": all_datasets}
    return obj


def main(fn):
    '''
    First sum all the interrupts on a given CPU thread for a particular timestamp
    Then subtract the total interrupts from previous timestamp
    '''
    with open(fn, 'r') as fid:
        blob = fid.read()
    blobs = blob.split('##TIMESTAMP## ')
    interrupts = False
    csv_str = ''
    for blob in blobs[1:]:
        try:
           (csv_line, interrupts) = format_line(blob.split('\n'), interrupts)
           csv_str += csv_line
        except Exception as e:
            err_str = "Problem extracting entry from %s\n" % fn
            err_str += "Error is %s\nEntry is %s\n" % (str(e), blob)
            sys.stderr.write(err_str)
            sys.exit(1)

    obj = csv_to_json(csv_str)
    out_fn = fn.replace('data/raw', 'data/final') + '.json'
    with open(out_fn, 'w') as fid:
        fid.write(json.dumps(obj))

if __name__ == '__main__':
    if (len(sys.argv) < 2):
        sys.stderr.write("USAGE: ./parse_interrupts.py <fn>\n")
        sys.exit(1)
    main(sys.argv[1])