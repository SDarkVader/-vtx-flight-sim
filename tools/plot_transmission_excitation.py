"""Plot excitation orders for the hypothetical 20:60 gear; not a modal plot."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/vtx-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

rpm=np.linspace(1100,1300,401)
sun=6016/4
mesh=20*np.abs(sun-rpm)/60
blade=4*rpm/60
fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained')
ax.plot(rpm,mesh,label='Sun–planet mesh excitation (20 teeth)',color='#126c73',linewidth=2)
ax.plot(rpm,blade,label='Four-blade passing excitation',color='#b75b22',linewidth=2)
ax.axhline(6016/60,color='#636d76',linestyle='--',label='Turbine shaft rotational frequency')
ax.set(xlabel='Illustrative fan speed (rpm)',ylabel='Excitation frequency (Hz)',
       title='VTX transmission concept: excitation frequencies')
ax.grid(alpha=.2);ax.legend(fontsize=9,loc='upper right')
fig.text(.02,.01,'Illustrative sweep; natural frequencies and permissible speed range are unknown. Crossings do not establish resonance.',fontsize=8)
fig.savefig(Path(__file__).resolve().parents[1]/'evidence/transmission_excitation_screen.png',dpi=170)
