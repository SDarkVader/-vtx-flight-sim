"""Exercise two independent ASGI observers against an isolated, resumable scenery session."""
import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import numpy as np

from vtx import live_server as server


async def inspect(data,key):
    lab = server.Laboratory(data)
    lab.start(server.Mission(environment=key, airframe_variant='phantom-a10c', departure=[-3885,0],
                             destination=[300,0], phantom={'start_configuration':'road'}))
    transport = httpx.ASGITransport(app=server.app)
    with patch.object(server, 'lab', lab):
        async with (httpx.AsyncClient(transport=transport,base_url='http://vtx.invalid') as pilot,
                    httpx.AsyncClient(transport=transport,base_url='http://vtx.invalid') as observer):
            async def command(client, door, opened):
                return await client.post('/api/scenery/iris',json=dict(environment=key,door=door,open=opened))

            async def both():
                a,b = [(await c.get('/api/view')).json() for c in (pilot,observer)]
                for field in ['environment','run_id','iris','scenery_time_s','course_timing']:
                    assert a[field] == b[field], field
                return dict(time=a['scenery_time_s'], iris=a['iris'])

            initial = await both()
            assert (await command(pilot,'south',True)).status_code == 422
            parent = lab.aircraft
            p = parent.data.qpos[:3].copy()
            west = lab.world.vaderland['operations']['annex']['doors'][0]
            parent.data.qpos[:3] = west['center']
            assert (await command(observer,west['id'],False)).status_code == 409
            parent.data.qpos[:3] = p
            assert (await command(pilot,'west',False)).status_code == 200
            while parent.data.time < .60:
                lab.integrate()
            closing = await both()
            assert 0 < closing['iris']['west'] < 1 and closing['iris']['east'] == 1
            assert (await command(observer,'west',True)).status_code == 200
            while parent.data.time < .8:
                lab.integrate()
            opening = await both()
            assert closing['iris']['west'] < opening['iris']['west'] < 1
            lab.checkpoint(force=True)
            qpos = parent.data.qpos.copy()
            userdata = parent.data.userdata.copy()
            saved = lab.world.timing.save()
            parent.step_log.close()
            lab.audit_file.close()
            recovered = server.Laboratory(data)
            assert recovered.paused and recovered.active and recovered.run_id == lab.run_id
            np.testing.assert_array_equal(recovered.aircraft.data.qpos,qpos)
            np.testing.assert_array_equal(recovered.aircraft.data.userdata,userdata)
            assert recovered.world.timing.save() == saved
            assert recovered.aircraft.scenery.doors(recovered.aircraft.data) == opening['iris']
            recovered.stop('Completed isolated two-observer iris recovery review')
            return dict(world=key, independent_observers=2, initial=initial, closing=closing, opening=opening,
                        invalid_portal=422, occupied_portal=409, controls='one shared active aircraft',
                        restored_native_checkpoint=True, matching_gate_data=userdata.tolist(), courses=list(saved['runs']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--world',default='vaderland-15')
    args = parser.parse_args()
    with TemporaryDirectory(dir=args.output.parent) as temp:
        result = asyncio.run(inspect(Path(temp),args.world))
    args.output.write_text(json.dumps(result,indent=2))
    print(result)
