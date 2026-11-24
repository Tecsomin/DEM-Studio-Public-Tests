import json
import math
import tempfile
import unittest
from pathlib import Path
import sys
_p=Path(__file__).resolve()
_repo_root=_p.parents[1]
_candidate=_repo_root / "experiments" / "nn01"
sys.path.insert(0, str(_candidate if _candidate.is_dir() else _p.parent))
import nn_broadphase_advisor as nn


def examples(n=45):
    cases=[]
    for i in range(n):
        particles=1000 + 300*i
        features={'particles':particles, 'fill_fraction':0.1+0.002*i,
                  'contact_ratio':0.05+0.004*i, 'velocity_rms':0.5+0.01*i,
                  'stl_triangles':100+i*20, 'moving_fraction':0.1}
        base=1 + i*.03
        times={'grid':base*(0.9 if i<15 else 1.2),
               'compact':base,
               'verlet':base*(0.9 if i>=28 else 1.2)}
        cases.append({'case_id':f'case_{i}','features':features,
                      'ms_per_step':times,'provenance':'synthetic'})
    return cases

class NnTests(unittest.TestCase):
    def test_reject_nan(self):
        f=examples()[0]['features']
        f['velocity_rms']=float('nan')
        with self.assertRaises(ValueError): nn.check_features(f)
    def test_reject_bad_timings(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.jsonl'
            rows=examples()
            rows[0]['ms_per_step']['grid']=0
            p.write_text('\n'.join(json.dumps(c) for c in rows))
            with self.assertRaises(ValueError): nn.read_cases(p)
    def test_reject_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.jsonl'; r=examples();r[2]['case_id']=r[0]['case_id']
            p.write_text('\n'.join(json.dumps(c) for c in r))
            with self.assertRaises(ValueError): nn.read_cases(p)
    def test_deterministic_training(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.jsonl';p.write_text('\n'.join(json.dumps(c) for c in examples()))
            data=nn.read_cases(p)
            a=nn.fit(data,epochs=30);b=nn.fit(data,epochs=30)
            self.assertEqual(a,b)
            self.assertFalse(a['production_approved'])
            self.assertGreater(a['holdout']['n_test'],1)
    def test_out_of_domain_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.jsonl';p.write_text('\n'.join(json.dumps(c) for c in examples()))
            model=nn.fit(nn.read_cases(p),epochs=30)
            feat=examples()[0]['features']
            feat['particles']=9000000
            out=nn.recommend(model,feat)
            self.assertEqual(out['reason'],'out_of_distribution_fallback')
            self.assertEqual(out['recommendation'],'compact')
            self.assertFalse(out['solver_changed'])
    def test_production_enabled_model_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.jsonl';p.write_text('\n'.join(json.dumps(c) for c in examples()))
            model=nn.fit(nn.read_cases(p),epochs=30)
            model['production_approved']=True
            with self.assertRaises(ValueError): nn.recommend(model,examples()[3]['features'])

if __name__=='__main__': unittest.main()