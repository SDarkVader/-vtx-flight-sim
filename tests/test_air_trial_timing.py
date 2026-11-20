from vtx.air_trial_timing import AirTrialTiming


def test_air_trial_checks_volume_direction_sequence_and_contacts():
    race = dict(name='Air Test', gates=[
        dict(center=[x,0.,150.],normal=[1.,0.,0.],right=[0.,1.,0.],
             up=[0.,0.,1.],width_m=24.,height_m=14.)
        for x in (0.,50.,100.)
    ])
    clock=AirTrialTiming([], [race])
    state=clock.runs['Air Test']
    clock.sample(0.,[-4.,0.,158.])
    clock.sample(.1,[4.,0.,158.])
    assert state['next']==0
    clock.sample(.2,[-4.,0.,150.])
    assert state['next']==0
    clock.sample(.3,[4.,0.,150.],air_allowed=False)
    assert state['next']==0
    clock.sample(.4,[-4.,0.,150.])
    clock.sample(.5,[4.,0.,150.])
    assert state['next']==1
    clock.sample(.6,[46.,0.,150.])
    clock.sample(.7,[55.,0.,150.])
    assert state['next']==2
    clock.sample(.8,[70.,0.,150.],contact=True)
    clock.sample(.9,[105.,0.,150.])
    assert state['last'] is None
    clock.sample(1.0,[-5.,0.,150.])
    clock.sample(1.1,[5.,0.,150.])
    clock.sample(1.2,[55.,0.,150.])
    clock.sample(1.3,[105.,0.,150.])
    assert state['laps']==1 and state['start'] is None and state['last']==.24