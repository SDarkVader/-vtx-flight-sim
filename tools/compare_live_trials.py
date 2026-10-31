"""Post-flight sensor comparison only; never reads an active run or sends inputs."""
from pathlib import Path
import argparse,json,math,gzip

ROOT=Path(__file__).resolve().parents[1]


def metrics(run):
    if not run.replace('-','').isalnum():raise ValueError('Invalid run ID')
    path=ROOT/'evidence/flights'/run
    if not (path/'summary.json').exists():raise ValueError('Completed, archived trials only')
    summary=json.loads((path/'summary.json').read_text())
    meta=json.loads((path/'metadata.json').read_text())
    event_path=path/'events.jsonl'
    if event_path.exists():
        with event_path.open() as f:events=[json.loads(s) for s in f]
    else:
        with gzip.open(path/'events.jsonl.gz','rt') as f:events=[json.loads(s) for s in f]
    obs=[e['payload'] for e in events if e['kind']=='observation']
    start_height=obs[0]['baro_m']
    # A disclosed instrument proxy: extension plus a measurable rise from parked.
    airborne_start=next((i for i,o in enumerate(obs) if o['t_s']>1 and
        max(o['gear_compression_m'])<.002 and o['baro_m']>start_height+.05),None)
    contact=None;phase=[]
    if airborne_start is not None:
        contact=next((i for i in range(airborne_start+1,len(obs))
            if max(obs[i]['gear_compression_m'])>.002),None)
        phase=obs[airborne_start:contact if contact is not None else len(obs)]
    def inclination(o):
        r,p,_=map(math.radians,o['attitude_xyz_deg'])
        return math.degrees(math.acos(max(-1.,min(1.,math.cos(r)*math.cos(p)))))
    request=meta['request'];provenance=meta['airframe']
    config={k:request.get(k) for k in ['departure','destination','reference_rpm','gear_variant','airframe_variant']}
    config.update(fuel_kg=request.get('fuel_kg',60.),engine_power_limit_kw=request.get('engine_power_limit_kw',469.8),
        runtime_source_sha256=meta['runtime_source_sha256'],ledger_sha256=provenance['ledger_sha256'])
    return dict(run_id=run,configuration=config,summary={k:summary[k] for k in
        ['outcome','reason','decisions','simulated_seconds','fuel_used_kg','max_airframe_origin_altitude_m']},
        airborne_sensor_proxy=(dict(start_t_s=phase[0]['t_s'],end_t_s=obs[contact]['t_s'] if contact is not None else phase[-1]['t_s'],
            duration_s=(obs[contact]['t_s'] if contact is not None else phase[-1]['t_s'])-phase[0]['t_s'],
            peak_inclination_deg=max(map(inclination,phase)),
            peak_world_angular_rate_norm_deg_s=max(math.sqrt(sum(v*v for v in o['gyro_world_deg_s'])) for o in phase),
            shaft_rpm_range=[min(min(o['rotor_rpm']) for o in phase),max(max(o['rotor_rpm']) for o in phase)],
            engine_kw_range=[min(o['engine_shaft_kw'] for o in phase),max(o['engine_shaft_kw'] for o in phase)],
            first_contact_vertical_speed_mps=obs[contact]['gnss_velocity_mps'][2] if contact is not None else None)
            if phase else None),
        final_instruments={k:obs[-1][k] for k in ['observation_id','gnss_xy_m','gnss_velocity_mps','attitude_xyz_deg','gear_compression_m','warning_lamps']})


def compare(first,second):
    a,b=metrics(first),metrics(second)
    different={k:[a['configuration'][k],b['configuration'][k]] for k in a['configuration']
        if a['configuration'][k]!=b['configuration'][k]}
    return dict(status='POST-FLIGHT SENSOR AUDIT ONLY',trials=[a,b],configuration_differences=different,
        interpretation='No differences in listed physics/configuration fields' if not different else
            'Configuration differs; do not attribute outcomes to pilot learning alone',
        limits='Noisy/quantized20Hz instruments; extension+rising barometer and compressed-gear contact proxies. First compressed-foot sample is excluded from airborne peaks. Sampled peaks are not400Hz extrema or proof of stability. Clock/decision timing differs between live attempts.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('first');p.add_argument('second');p.add_argument('--out',type=Path)
    args=p.parse_args();result=compare(args.first,args.second)
    text=json.dumps(result,indent=2)
    if args.out:args.out.write_text(text)
    print(text)
