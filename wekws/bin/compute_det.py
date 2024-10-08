# Copyright (c) 2021 Binbin Zhang(binbzha@qq.com)
#               2022 Shaoqing Yu(954793264@qq.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
import numpy as np
from tqdm import tqdm

def load_label_and_score(keyword, label_file, score_file):
    # score_table: {uttid: [keywordlist]}
    score_table = {}
    with open(score_file, 'r', encoding='utf8') as fin:
        for line in fin:
            arr = line.strip().split()
            key = arr[0]
            current_keyword = arr[1]
            str_list = arr[2:]
            if int(current_keyword) == keyword:
                scores = list(map(float, str_list))
                if key not in score_table:
                    score_table.update({key: scores})
    keyword_table = {}
    filler_table = {}
    filler_duration = 0.0
    with open(label_file, 'r', encoding='utf8') as fin:
        for line in fin:
            obj = json.loads(line.strip())
            assert 'key' in obj
            assert 'txt' in obj
            assert 'duration' in obj
            key = obj['key']
            index = obj['txt']
            duration = obj['duration']
            assert key in score_table
            if index == keyword:
                keyword_table[key] = score_table[key]
            else:
                filler_table[key] = score_table[key]
                filler_duration += duration
    return keyword_table, filler_table, filler_duration


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='compute det curve')
    parser.add_argument('--test_data', required=True, help='label file')
    parser.add_argument('--keyword', type=int, default=0, help='keyword label')
    parser.add_argument('--score_file', required=True, help='score file')
    parser.add_argument('--step', type=float, default=0.01,
                        help='threshold step')
    parser.add_argument('--window_shift', type=int, default=50,
                        help='window_shift is used to skip the frames after triggered')
    parser.add_argument('--stats_file',
                        required=True,
                        help='false reject/alarm stats file')
    parser.add_argument('--threshold_lower', type=float, default=0,
                        help='lower bound of threshold')
    parser.add_argument('--threshold_upper', type=float, default=1.0,
                        help='upper bound of threshold')
    args = parser.parse_args()
    window_shift = args.window_shift
    keyword_table, filler_table, filler_duration = load_label_and_score(
        args.keyword, args.test_data, args.score_file)
    print('Filler total duration Hours: {}'.format(filler_duration / 3600.0))

    # preprocess the score_table to avoid unnecessary traverse
    for key, score_list in keyword_table.items():
        keyword_table[key] = max(score_list)
    # auxiliary variable for skipping traverse on some negative samples
    _filler_table_max = {key: max(score_list) for key, score_list in filler_table.items()}
    threshold_lower, threshold_upper = args.threshold_lower, args.threshold_upper

    with open(args.stats_file, 'w', encoding='utf8') as fout:
        keyword_index = int(args.keyword)
        thresholds = np.arange(threshold_lower, threshold_upper + args.step, args.step)
        for threshold in tqdm(thresholds):
        # while threshold <= threshold_upper:
            # transverse the all keyword_table
            num_false_reject = sum(1 for key, score in keyword_table.items() if score < threshold)
            
            # transverse the all filler_table
            num_false_alarm = 0
            for key, score_list in filler_table.items():
                # skip unnecessary traverse on negative samples, which costs a lot of unnecessary time in my case
                if _filler_table_max[key] < threshold:
                    continue
                # traverse the score_list
                i = 0
                while i < len(score_list):
                    if score_list[i] >= threshold:
                        num_false_alarm += 1
                        i += window_shift
                    else:
                        i += 1
            if len(keyword_table) != 0:
                false_reject_rate = num_false_reject / len(keyword_table)
            num_false_alarm = max(num_false_alarm, 1e-6)
            if filler_duration != 0:
                false_alarm_per_hour = num_false_alarm / \
                    (filler_duration / 3600.0)
            fout.write('{:.6f} {:.6f} {:.6f}\n'.format(threshold,
                                                       false_alarm_per_hour,
                                                       false_reject_rate))
            # threshold += args.step
