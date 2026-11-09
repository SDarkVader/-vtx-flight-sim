from pathlib import Path
p=Path(__file__).resolve().parents[1]/'src/vtx/live_server.py'
s=p.read_text(encoding='utf-8')
needle='    def retry(self,request):\n'
assert s.count(needle)==1
method='''    def reset_after_failure(self, reason):
        """Retain a failed run and its evidence before starting a new test."""
        if not self.active:
            raise HTTPException(409, 'No active flight to reset')
        run_id = self.run_id
        run_path = self.log_path
        objective = self.objective
        pilot = self.pilot_owner
        config = dict(getattr(self.aircraft, 'provenance', {}))
        result = self.stop(reason)
        pilot_summary = dict(run_id=run_id, reason=reason, outcome=result['outcome'],
                             objective=objective, pilot_id=pilot,
                             decision_count=result['decisions'],
                             simulated_seconds=result['simulated_seconds'],
                             evidence=['summary.json', 'events.jsonl'])
        findings = dict(run_id=run_id, evidence_state='measured_simulation',
                        configuration=config, outcome=result['outcome'],
                        max_airframe_origin_altitude_m=result['max_airframe_origin_altitude_m'],
                        max_contact_force_n=result['max_contact_force_n'],
                        max_gear_load_n=result['max_gear_load_n'],
                        max_nongear_impact_n=result['max_nongear_impact_n'],
                        fuel_used_kg=result['fuel_used_kg'],
                        causal_analysis='Not assessed',
                        next_action='Review telemetry and identify the failure mechanism.')
        (run_path/'pilot_summary.json').write_text(json.dumps(pilot_summary,indent=2,default=float),encoding='utf-8')
        (run_path/'engineering_findings.json').write_text(json.dumps(findings,indent=2,default=float),encoding='utf-8')
        # A fresh manual run is deliberately distinct from resuming the failed state.
        new = self.retry({'authority':'manual'})
        return dict(previous_run_id=run_id, new_run_id=new['run_id'],
                    pilot_summary='pilot_summary.json', engineering_findings='engineering_findings.json')

'''
s=s.replace(needle,method+needle)
needle="    previous=lab.pilot_owner;lab.pending_pilot=None\n    lab.pilot_epoch+=1\n    try:\n"
assert s.count(needle)==1
start=s.index(needle);end=s.index("@app.get('/api/validate')",start)
s=s[:start]+"    lab.log('pilot_provider_failed',dict(pilot_id=lab.pilot_owner,reason=reason.strip(),pilot_epoch=lab.pilot_epoch))\n    return lab.reset_after_failure('Pilot provider failed: '+reason.strip())\n"+s[end:]
needle="            phantom_live.integrate(self);self.compact_actions();return\n"
assert s.count(needle)==1
s=s.replace(needle,"            phantom_live.integrate(self);self.compact_actions()\n            if p.crashed:self.reset_after_failure('Physical crash detected')\n            return\n")
needle="        p.step()\n        if p.data.time-self.last_audit_t>=.05:\n"
assert s.count(needle)==1
s=s.replace(needle,"        p.step()\n        if p.crashed:\n            self.reset_after_failure('Physical crash detected')\n            return\n        if p.data.time-self.last_audit_t>=.05:\n")
p.write_text(s,encoding='utf-8',newline='\n')
