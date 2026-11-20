"""Monumental original aviator, sculpted in standing-human proportions and cast at civic scale."""
import math


def statue(m,cx,cy,z):
    scale=24.;motion=dict(name='aviator',origin=[cx,cy,z],period_s=120.)
    def sculpt(name,levels,finish,parent):
        return m.rings('aviator-'+name,[(cx+scale*x,cy+scale*y,a*scale,b*scale,z+h*scale) for x,y,a,b,h in levels],
                       finish,33,parent=parent,motion=motion)
    def relief(name,coords,finish,parent):
        return m.hull('aviator-'+name,[[cx+scale*x,cy+scale*y,z+scale*h] for x,y,h in coords],
                      finish,parent=parent,motion=motion)
    for s in (-1,1):
        x=.177*s;y=.052*s
        boot=sculpt('flight-boot'+str(s),[(x,y-.054,.093,.184,-.004),(x,y-.057,.100,.190,.044),
             (x,y-.036,.094,.155,.094),(x,y+.018,.074,.086,.151),(x,y+.018,.07,.085,.22)],'leather','civic-turntable')
        shin=sculpt('gaiter'+str(s),[(x,y+.018,.072,.079,.14),(x,y+.02,.081,.087,.255),
             (x*.91,y+.034,.086,.082,.413),(x*.91,y+.036,.080,.081,.50)],'patina',boot)
        thigh=sculpt('riding-trouser'+str(s),[(x*.91,y+.030,.081,.086,.46),(x*.92,y+.031,.098,.096,.52),
             (x*.89,y+.01,.120,.113,.677),(x*.78,y,.132,.127,.83),(x*.68,0,.127,.128,.946)],'patina',shin)
        sculpt('boot-strap'+str(s),[(x,y+.018,.083,.094,.163),(x,y+.018,.084,.093,.183)],'brightbronze',boot)
    pelvis=sculpt('flyer-jacket-skirt',[(.004,.020,.254,.145,.80),(0,.013,.251,.152,.88),
                 (0,.006,.199,.130,1.014),(0,0,.19,.127,1.07)],'bronze','aviator-riding-trouser-1')
    trunk=sculpt('bomber-jacket',[(0,0,.187,.134,.976),(0,-.004,.194,.137,1.077),
                  (.003,.004,.249,.169,1.25),(.009,.025,.283,.151,1.364),(.014,.022,.231,.137,1.416),
                  (.019,.014,.128,.10,1.474)],'bronze',pelvis)
    belt=sculpt('harness-belt',[(0,-.001,.200,.144,1.005),(.001,-.002,.202,.143,1.043)],'darkbronze',trunk)
    collar=sculpt('shearling-collar',[(.014,.021,.138,.111,1.387),(.016,.024,.158,.126,1.433),(.024,.014,.111,.10,1.484)],'brightbronze',trunk)
    neck=sculpt('neck',[(.026,.015,.079,.083,1.427),(.026,.013,.073,.072,1.546)],'bronze',collar)
    head=sculpt('face',[(.029,-.042,.050,.073,1.50),(.032,-.020,.083,.097,1.533),
          (.032,.002,.104,.104,1.60),(.034,.008,.113,.106,1.675),(.034,.009,.104,.101,1.729),
          (.033,.006,.075,.082,1.763)],'brightbronze',neck)
    sculpt('nose',[(.034,-.092,.032,.040,1.588),(.034,-.091,.030,.059,1.615),(.036,-.089,.019,.032,1.663)],'brightbronze',head)
    cap=sculpt('leather-flight-cap',[(.032,.016,.113,.108,1.657),(.035,.017,.117,.111,1.709),
          (.035,.019,.093,.100,1.768),(.034,.019,.054,.064,1.792)],'leather',head)
    for s in (-1,1):
        sculpt('goggle-rim'+str(s),[(.034+s*.052,-.086,.046,.032,1.627),(.034+s*.052,-.089,.051,.035,1.656),
               (.034+s*.052,-.087,.047,.030,1.680)],'brightbronze',head)
        sculpt('goggle-glass'+str(s),[(.034+s*.052,-.111,.038,.018,1.640),(.034+s*.052,-.114,.041,.021,1.656),
               (.034+s*.052,-.111,.039,.018,1.670)],'visor',head)
        sculpt('ear-cup'+str(s),[(.034+s*.104,.015,.020,.048,1.600),(.034+s*.105,.015,.032,.058,1.651),
               (.034+s*.104,.015,.023,.047,1.695)],'leather',cap)
    # Left glove lifts to the brow. Opposite hand carries a flying helmet clear of the hip.
    sleeve=sculpt('salute-sleeve',[(.357,.030,.064,.071,1.268),(.354,.032,.075,.083,1.306),
          (.284,.028,.084,.096,1.386),(.226,.025,.087,.105,1.409)],'bronze',trunk)
    fore=sculpt('salute-gauntlet',[(.357,.022,.073,.079,1.284),(.348,.003,.074,.076,1.346),
          (.258,-.041,.064,.064,1.502),(.194,-.055,.048,.05,1.612)],'bronze',sleeve)
    sculpt('salute-glove',[(.195,-.055,.051,.051,1.578),(.18,-.060,.055,.049,1.634),
          (.121,-.077,.062,.043,1.662),(.088,-.093,.024,.032,1.679)],'leather',fore)
    sleeve=sculpt('relaxed-sleeve',[(-.297,.020,.067,.074,1.025),(-.297,.016,.081,.083,1.095),
          (-.266,.017,.088,.095,1.273),(-.225,.027,.096,.1,1.397)],'bronze',trunk)
    arm=sculpt('relaxed-gauntlet',[(-.294,-.044,.055,.063,.808),(-.317,-.028,.070,.073,.95),
          (-.297,.014,.077,.084,1.081)],'bronze',sleeve)
    hand=sculpt('helmet-hand',[(-.290,-.092,.046,.067,.757),(-.296,-.071,.052,.060,.837),
          (-.295,-.052,.057,.064,.868)],'leather',arm)
    helmet=sculpt('carried-helmet',[(-.30,-.099,.10,.105,.526),(-.31,-.106,.128,.140,.556),
        (-.324,-.115,.142,.146,.646),(-.323,-.109,.133,.130,.718),(-.31,-.104,.083,.084,.789)],'brightbronze',hand)
    sculpt('helmet-visor', [(-.318,-.217,.098,.049,.590),(-.321,-.232,.111,.044,.645),
           (-.322,-.220,.105,.051,.685)],'visor',helmet)
    relief('mouth',[(x,y,h) for x,h in [(-.010,1.565),(.036,1.556),(.078,1.570),(.034,1.568)] for y in [-.102,-.115]],'darkbronze',head)
    for n in range(4):
        shift=n*.015
        sculpt('salute-finger-'+str(n),[(.09,-.104+shift,.035,.011,1.655),(.087,-.104+shift,.038,.010,1.670)],'leather','aviator-salute-glove')
    for s in [-1,1]:
        relief('crest-'+str(s),[(s*x,y,h) for x,h in [(0.,1.18),(.155,1.326),(.140,1.344),(.015,1.253)] for y in [-.148,-.168]],'gold',trunk)
        relief('lapel-'+str(s),[(s*x,y,h) for x,h in [(.026,1.30),(.149,1.408),(.102,1.43)] for y in [-.09,-.128]],'brightbronze',trunk)
    return dict(center=[cx,cy,z],period_s=120.,figure_height_m=round(1.796*scale,2))
