"""Audit and regression checks for failures discovered in the publication review."""
from pathlib import Path
import copy
import json
import subprocess
import sys
import tempfile
import unittest

from run_phase_space import make_jobs, validate_resume_ledger
from scripts.audit_experiment import displayed_matrix, oracle_decision, oracle_joint

ROOT=Path(__file__).resolve().parents[1]


class ExperimentAuditTests(unittest.TestCase):
    def test_independent_oracle_handles_column_offdiagonal(self):
        matrix={('C','C'):(3,3),('C','D'):(0,5),('D','C'):(5,0),('D','D'):(1,1)}
        r=oracle_joint(matrix,'C','D',2,1)
        self.assertEqual(r['welfare'],5)
        self.assertEqual((r['row_regret'],r['column_regret']),(.5,0))
        self.assertFalse(r['nash'])
        for role in ('row','column'):
            b=oracle_decision(matrix,role,'C',.5,2)
            self.assertEqual(b['stated_belief_regret_normalized'],.75)
            self.assertEqual(b['stated_belief_best_response'],'D')

    def test_prompt_oracle_transposes_column_own_perspective(self):
        record={'case':{'stage':'perspective_grid','replicate':1},'role':'column','request':{'messages':[{'content':
            'your action=B, opponent action=B: (your payoff 3, opponent payoff 3)\n'
            'your action=B, opponent action=A: (your payoff 0, opponent payoff 5)\n'
            'your action=A, opponent action=B: (your payoff 5, opponent payoff 0)\n'
            'your action=A, opponent action=A: (your payoff 1, opponent payoff 1)'}]}}
        matrix=displayed_matrix(record)
        self.assertEqual(matrix['C','D'],(0,5))
        self.assertEqual(matrix['D','C'],(5,0))
        record['request']['messages'][0]['content'] += '\nyour action=A, opponent action=A: (your payoff 1, opponent payoff 1)'
        with self.assertRaises(AssertionError):displayed_matrix(record)

    def test_duplicate_models_rejected_before_scheduling(self):
        with self.assertRaises(ValueError):make_jobs('pilot',0,['glm','glm'])
        with self.assertRaises(ValueError):make_jobs('pilot',0,[])

    def test_missing_ledger_cannot_reset_existing_spending(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            ledger={'completed_attempts':0,'accounted_usd':0,'reported_usd':0,'reservations':{}}
            prior=[{'job_id':'a','accounted_cost_usd':1,'reported_cost_usd':1}]
            with self.assertRaisesRegex(ValueError,'no budget ledger'):validate_resume_ledger(root,ledger,prior)
            (root/'manifest_grid_0.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'no budget ledger'):validate_resume_ledger(root,ledger,[])

    def test_crash_between_log_and_ledger_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'ledger.json').write_text('{}')
            ledger={'completed_attempts':0,'accounted_usd':2,'reported_usd':0,'reservations':{'a':2}}
            prior=[{'job_id':'a','accounted_cost_usd':1,'reported_cost_usd':1}]
            with self.assertRaisesRegex(ValueError,'still have reservations'):validate_resume_ledger(root,ledger,prior)

    def test_unreturned_reservation_remains_charged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'ledger.json').write_text('{}')
            ledger={'completed_attempts':1,'accounted_usd':3,'reported_usd':1,'reservations':{'pending':2}}
            prior=[{'job_id':'a','accounted_cost_usd':1,'reported_cost_usd':1}]
            validate_resume_ledger(root,ledger,prior)
            bad=copy.deepcopy(ledger);bad['accounted_usd']=1
            with self.assertRaisesRegex(ValueError,'Recorded costs differ'):validate_resume_ledger(root,bad,prior)
            bad=copy.deepcopy(ledger);bad['reported_usd']=float('nan')
            with self.assertRaisesRegex(ValueError,'Invalid budget'):validate_resume_ledger(root,bad,prior)

    def test_reproduction_refuses_to_overwrite_different_records(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);raw=out/'attempts.jsonl';raw.write_text('different original records\n')
            result=subprocess.run([sys.executable,str(ROOT/'reproduce.py'),'--output',str(out)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('different raw records',result.stderr)
            self.assertEqual(raw.read_text(),'different original records\n')
            self.assertFalse((out/'ledger.json').exists())

    def test_reproduction_refuses_source_subdirectory(self):
        out=ROOT/'data'/'must-not-be-created'
        self.assertFalse(out.exists())
        result=subprocess.run([sys.executable,str(ROOT/'reproduce.py'),'--output',str(out)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('outside the source data',result.stderr)
        self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
