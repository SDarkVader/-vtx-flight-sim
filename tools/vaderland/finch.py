"""Install the measured canonical meshes in Arthur's office and give him a level inspection walk."""
import json
import numpy as np


def install(m,path):
    src=json.loads(path.read_text());cx,cy=1000.,-342.2
    root=np.array([cx+3.2,cy,10.8])
    moves={}
    for part in ['body','upper_arm.R','thigh.L','thigh.R']:
        offset=src['origins'].get(part,[0,0,0])
        moves[part]=dict(name='finch-'+part,origin=(root+offset).tolist(),root=root.tolist(),
            orbit=[cx,cy,3.2,1.12],period_s=28.,strides=23,swing_rad={'thigh.L':.30,'thigh.R':-.30,'upper_arm.R':.22}.get(part,0))
    parents={'torso':'thigh.L','head':'torso','upper_arm.R':'torso','arm-l':'torso','hand-board':'arm-l'}
    for name,vertices in src['staff'].items():
        p=parents.get(name)
        m.hull('finch-'+name,root+np.array(vertices),'staff',motion=moves.get(name,moves['body']),
               parent='finch-'+p if p else 'office-gallery-floor',source_visual=True)
    chair=m.rings('office-chair-foot',[(998.2,-345.65,.46,.42,10.77),(998.2,-345.65,.43,.40,10.886),
        (998.2,-345.65,.135,.13,11.18)],'bronze',21,parent='office-gallery-floor')
    m.box('office-records-mount',1006.2,-345.15,10.77,13.15,1.62,.077,'walnut',parent='office-gallery-floor')
    for name,vertices in src['furniture'].items():
        parent={'Raymond_ExecutiveThrone':chair,'Arthur_Corkboard':'office-records-mount',
                'Arthur_TaskLamp':'office-Arthur_InvestigationDesk','Raymond_DeskProps':'office-Raymond_ExecutiveDesk'}.get(name)
        m.hull('office-'+name,np.array(vertices)+[575.2,-8.3,10.8],'furniture',parent=parent or 'office-gallery-floor',source_visual=True)
    return moves
