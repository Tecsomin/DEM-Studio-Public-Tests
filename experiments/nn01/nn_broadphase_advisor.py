#!/usr/bin/env python3
"""DEM Studio NN-01: reproducible, advisory-only broad-phase performance estimator.

This is not a DEM solver. It trains on measured whole-step runtimes and must
never switch the physics kernel automatically. Synthetic fixtures do not certify
acceleration. Copyright (c) 2026 Chile Ingenieria SPA. All rights reserved.
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

ALGORITHMS = ('grid', 'compact', 'verlet')
FEATURES = ('particles', 'fill_fraction', 'contact_ratio', 'velocity_rms',
            'stl_triangles', 'moving_fraction')
FEATURE_BOUNDS = ((2, 10000000), (0, 1), (0, 1), (0, 1e6), (0, 1e8), (0, 1))


def check_features(raw):
    if set(raw) != set(FEATURES):
        raise ValueError('Features must exactly match declared schema')
    values = [float(raw[k]) for k in FEATURES]
    for k, v, (lo, hi) in zip(FEATURES, values, FEATURE_BOUNDS):
        if not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError('Nonfinite/out-of-bounds feature: ' + k)
    if values[0] != int(values[0]) or values[4] != int(values[4]):
        raise ValueError('Count features must be integral')
    values[0] = math.log1p(values[0])
    values[4] = math.log1p(values[4])
    return values


def read_cases(file):
    result = []
    names = set()
    for line in Path(file).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict) or set(obj) != {'case_id', 'features', 'ms_per_step', 'provenance'}:
            raise ValueError('Incorrect input schema')
        case = str(obj['case_id'])
        if not case or case in names:
            raise ValueError('Missing/duplicate case_id')
        names.add(case)
        x = check_features(obj['features'])
        perf = obj['ms_per_step']
        if not isinstance(perf, dict) or set(perf) != set(ALGORITHMS):
            raise ValueError('Timings must contain all algorithms on the same case')
        times = [float(perf[a]) for a in ALGORITHMS]
        if any(not math.isfinite(t) or t <= 0 for t in times):
            raise ValueError('Invalid full-step timing')
        if obj['provenance'] not in ('synthetic', 'measured'):
            raise ValueError('Invalid provenance')
        result.append({'case_id': case, 'x': x, 'y': [math.log(t) for t in times],
                       'times': times, 'provenance': obj['provenance']})
    if len(result) < 15:
        raise ValueError('At least 15 distinct cases required')
    return result


def normalize(x, center, scale):
    return [(v - c) / s for v, c, s in zip(x, center, scale)]


def predict_raw(model, x):
    xx = normalize(x, model['center'], model['scale'])
    h = [math.tanh(sum(w*v for w, v in zip(row, xx)) + b)
         for row, b in zip(model['w1'], model['b1'])]
    return [sum(w*v for w, v in zip(row, h)) + b
            for row, b in zip(model['w2'], model['b2'])], h, xx


def fit(cases, epochs=900, learning_rate=0.012, seed=2026):
    if epochs < 1 or learning_rate <= 0 or not math.isfinite(learning_rate):
        raise ValueError('Invalid training parameters')
    train = [c for c in cases if int(hashlib.sha256(c['case_id'].encode()).hexdigest(), 16) % 5]
    test = [c for c in cases if not int(hashlib.sha256(c['case_id'].encode()).hexdigest(), 16) % 5]
    if len(test) < 2 or len(train) < 10:
        raise ValueError('Dataset cannot yield usable grouped holdout')
    center = [sum(c['x'][i] for c in train)/len(train) for i in range(len(FEATURES))]
    scale = [max(1e-9, (sum((c['x'][i]-center[i])**2 for c in train)/len(train))**.5)
             for i in range(len(FEATURES))]
    rng = random.Random(seed)
    width = 10
    w1 = [[rng.uniform(-.2, .2) for _ in FEATURES] for _ in range(width)]
    w2 = [[rng.uniform(-.2, .2) for _ in range(width)] for _ in ALGORITHMS]
    model = {'schema': 1, 'algorithms': list(ALGORITHMS), 'features': list(FEATURES),
             'center': center, 'scale': scale, 'w1': w1, 'w2': w2,
             'b1': [0.0]*width, 'b2': [sum(c['y'][i] for c in train)/len(train)
                                      for i in range(len(ALGORITHMS))],
             'train_feature_min': [min(c['x'][i] for c in train) for i in range(len(FEATURES))],
             'train_feature_max': [max(c['x'][i] for c in train) for i in range(len(FEATURES))],
             'production_approved': False,
             'source': 'measured' if all(c['provenance']=='measured' for c in cases) else 'includes_synthetic'}
    for _ in range(epochs):
        for c in train:
            output, h, xx = predict_raw(model, c['x'])
            errors = [max(-10, min(10, p-y)) for p, y in zip(output, c['y'])]
            hidden_error = [sum(errors[j]*w2[j][i] for j in range(3)) * (1-h[i]*h[i])
                            for i in range(width)]
            for j in range(3):
                for i in range(width):
                    w2[j][i] -= learning_rate*errors[j]*h[i]
                model['b2'][j] -= learning_rate*errors[j]
            for i in range(width):
                for k in range(len(FEATURES)):
                    w1[i][k] -= learning_rate*hidden_error[i]*xx[k]
                model['b1'][i] -= learning_rate*hidden_error[i]
    correct = 0
    improvements = []
    for c in test:
        output, _, _ = predict_raw(model, c['x'])
        recommended = min(range(3), key=lambda i:output[i])
        optimal = min(range(3), key=lambda i:c['times'][i])
        correct += recommended == optimal
        improvements.append((c['times'][1] - c['times'][recommended])/c['times'][1])
    model['holdout'] = {
        'n_train': len(train), 'n_test': len(test),
        'selection_accuracy': correct/len(test),
        'mean_speedup_vs_compact_observed_if_selected': sum(improvements)/len(improvements),
        'evaluation_scope': 'synthetic_only' if model['source'] != 'measured' else 'measured_cases_only'
    }
    return model


def recommend(model, raw):
    if model.get('schema') != 1 or model.get('algorithms') != list(ALGORITHMS) or model.get('production_approved') is not False:
        raise ValueError('Untrusted or production-enabled model')
    if model.get('features') != list(FEATURES):
        raise ValueError('Feature schema mismatch')
    x = check_features(raw)
    in_domain = all(lo <= v <= hi for v,lo,hi in zip(x, model['train_feature_min'], model['train_feature_max']))
    output, _, _ = predict_raw(model, x)
    predicted = [math.exp(max(-100, min(100, v))) for v in output]
    recommended = ALGORITHMS[min(range(3),key=lambda i:predicted[i])] if in_domain else 'compact'
    return {'recommendation': recommended if in_domain else 'compact',
            'reason': 'advisory_in_domain' if in_domain else 'out_of_distribution_fallback',
            'prediction_ms_per_step': dict(zip(ALGORITHMS,predicted)),
            'production_approved': False, 'solver_changed': False,
            'no_speedup_claim': True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    subs=p.add_subparsers(dest='command', required=True)
    tr=subs.add_parser('train')
    tr.add_argument('--cases',required=True)
    tr.add_argument('--out',required=True)
    tr.add_argument('--epochs',type=int,default=900)
    pr=subs.add_parser('recommend')
    pr.add_argument('--model',required=True)
    pr.add_argument('--features-json',required=True)
    args=p.parse_args()
    if args.command=='train':
        data=read_cases(args.cases)
        model=fit(data, epochs=args.epochs)
        Path(args.out).write_text(json.dumps(model,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps({'status':'PROTOTYPE_ONLY','model_file':args.out,'holdout':model['holdout']}))
    else:
        model=json.loads(Path(args.model).read_text(encoding='utf-8'))
        print(json.dumps(recommend(model,json.loads(Path(args.features_json).read_text(encoding='utf-8')))))

if __name__=='__main__':
    main()