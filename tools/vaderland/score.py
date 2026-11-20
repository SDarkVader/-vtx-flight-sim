"""Render Vaderland's original 16-bar score variations on a shared 96 BPM transport."""
import argparse
import math
from pathlib import Path
import subprocess
import wave

import numpy as np
from scipy.signal import butter, sosfilt


RATE = 24000
BEAT = .625
LENGTH = 64*BEAT
CHORDS = [(40, 55, 59, 62, 66), (36, 55, 59, 64, 67),
          (45, 55, 59, 60, 64), (38, 54, 57, 62, 64)]
# One motif, with space for wind, transients and the engine in each arrangement.
MOTIF = [(1.5, 71), (2.5, 74), (3.5, 78), (5., 76), (6.5, 71),
         (9.5, 69), (10.5, 71), (11.5, 76), (13., 74), (15., 66)]
PALETTES = {
    'airport': (.79, .52, .32, .18, 'keys'),
    'highlands': (.92, .45, .12, .16, 'strings'),
    'meridian': (.64, .72, .52, .54, 'keys'),
    'harbour': (.67, .44, .20, .32, 'bells'),
    'cathedral': (.68, .64, .52, .46, 'bells'),
    'event': (.43, .81, .76, 1.0, 'keys'),
}


def envelope(t, attack, release):
    return np.sin(np.pi/2*np.clip(t/attack, 0, 1))**2 * np.sin(
        np.pi/2*np.clip((t[-1]-t)/release, 0, 1))**2


def render(name):
    pad, lead, bass, drums, instrument = PALETTES[name]
    mix = np.zeros((round(LENGTH*RATE), 2))
    rng = np.random.default_rng(1150)
    def put(signal, time, level, pan=0):
        indices = (np.arange(signal.size)+round(time*RATE)) % len(mix)
        mix[indices, :] += level*signal[:, None]*np.sqrt(np.array([1-pan,1+pan])/2)
    def tone(beat, note, duration, level, pan, voice):
        t = np.arange(round(duration*RATE))/RATE
        f = 440*2**((note-69)/12)
        p = math.tau*f*t
        if voice == 'pad':
            amp = envelope(t,.62,.84)
            sound = (.48*np.sin(p)+.23*np.sin(p*.997)+.17*np.sin(p*1.004+.7)+.12*np.sin(2*p))
        elif voice == 'strings':
            amp = envelope(t,.23,.6)
            sound = .65*np.sin(p+.11*np.sin(31*t))+.23*np.sin(2*p+.3)+.10*np.sin(3*p)
        elif voice == 'bass':
            amp = envelope(t,.025,.17)*(.68+.32*np.exp(-3*t))
            sound = .70*np.sin(p)+.24*np.sin(2*p)+.11*np.sin(3*p)
        else:
            amp = envelope(t,.012,.38)*np.exp(-t*(1.55 if voice=='bells' else 2.4))
            mod = (1.45*np.sin(2.01*p) if voice=='bells' else .62*np.sin(2*p))*np.exp(-5*t)
            sound = .72*np.sin(p+mod)+.19*np.sin(2*p)+.09*np.sin(4*p)*np.exp(-6*t)
        out = sound*amp
        start = beat*BEAT
        put(out,start,level,pan)
        if voice in ('keys','bells','strings'):
            put(out,start+.3125,level*.20,-.75*pan)
            put(out,start+.625,level*.10,.60*pan)

    for bar in range(16):
        root, *notes = CHORDS[bar%len(CHORDS)]
        for i,n in enumerate(notes):
            tone(bar*4-.16+i*.075,n,3.18,.072*pad,[-.72,.64,-.36,.39][i],'pad')
        tone(bar*4,root,1.24,.16*bass,-.06,'bass')
        if name in ('event','meridian','cathedral'):
            tone(bar*4+2.5,root,.67,.14*bass,.09,'bass')
        if name in ('event','cathedral'):
            tone(bar*4+3.5,root+12,.34,.068*bass,.24,'bass')
        if (bar//4)%2==0 or name in ('event','meridian'):
            tone(bar*4+.5,notes[bar%4]+12,.78,.039*lead,.58,instrument)
        for at in (0.,2.):
            t = np.arange(round(.34*RATE))/RATE
            kick = np.sin(math.tau*(48*t+4.0*(1-np.exp(-t*34))))*np.exp(-t*15)*np.minimum(t/.006,1)
            put(kick,(bar*4+at)*BEAT,.115*drums)
        for at in (1.,2.5,3.5):
            t = np.arange(round(.23*RATE))/RATE
            noise = sosfilt(butter(2,[(1180 if at==1. else 3600),8200],'bandpass',fs=RATE,output='sos'),rng.normal(size=t.size))
            strike = noise*np.exp(-t*(23 if at==1. else 68))*np.minimum(t/.004,1)
            put(strike,(bar*4+at)*BEAT,.058*drums,.33 if at==1 else -.46)
    for verse in range(4):
        if verse==1 and name in ('highlands','harbour'):
            continue
        for beat,note in MOTIF:
            tone(verse*16+beat,note,1.05,.11*lead,-.25 if verse%2 else .32,instrument)
    return np.int16(np.tanh(mix*1.8)*32767)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for name in PALETTES:
        samples = render(name)
        subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-y',
                        '-f','s16le','-ar',str(RATE),'-ac','2','-i','pipe:0','-vn',
                        '-c:a','libopus','-b:a','64k',str(args.output/(name+'.ogg'))],
                       input=samples.astype('<i2').tobytes(),check=True)
        print(name, round(np.max(abs(samples))/32767,3), LENGTH, flush=True)


if __name__ == '__main__':
    main()
