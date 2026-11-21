const kindNames = {descent:'Downhill', glider:'Paragliding', base:'BASE jump',
  rocket:'Rocket pack', zipline:'Zip line'};

const metres = value => `${Math.round(value).toLocaleString()} m`;

export function createAlpineExplorer({trigger, dialog, showView}) {
  const zoneSelect=dialog.querySelector('#alpine-zone');
  const routeSelect=dialog.querySelector('#alpine-route');
  const zoneInfo=dialog.querySelector('#alpine-zone-info');
  const routeInfo=dialog.querySelector('#alpine-route-info');
  const actions=[...dialog.querySelectorAll('[data-alpine-view]')];
  let alpine;

  const zone = () => alpine.zones.find(item=>item.id===zoneSelect.value);
  const route = () => alpine.routes.find(item=>item.id===routeSelect.value);

  function option(label, value) {
    const entry=document.createElement('option');
    entry.textContent=label;entry.value=value;
    return entry;
  }

  function describe() {
    const item=route();
    if(!item){routeInfo.textContent='Choose a route to inspect its alignment.';return;}
    const change=item.start-item.end;
    const details=[item.grade, kindNames[item.kind]??'Lift', `${metres(item.distance)} along the map`,
      `${metres(item.highPoint)} highest waypoint`];
    if(Math.abs(change)>1)details.push(`${metres(Math.abs(change))} terrain ${change>0?'drop':'rise'}`);
    if(Number.isFinite(item.clearance))details.push(`${metres(item.clearance)} minimum straight-span clearance`);
    if(item.kind==='descent')details.push(`${Math.round(item.steepest*100)}% steepest sampled terrain grade`);
    routeInfo.textContent=details.filter(Boolean).join(' · ');
  }

  function chooseZone() {
    const current=zone();
    zoneInfo.textContent=`${current.area} · ${metres(current.elevation)} elevation`;
    const links=alpine.routes.filter(item=>item.from===current.id||item.to===current.id);
    routeSelect.replaceChildren(...links.map(item=>option(item.name,item.id)));
    describe();
  }

  trigger.onclick=()=>dialog.showModal();
  zoneSelect.onchange=chooseZone;
  routeSelect.onchange=describe;
  for(const button of actions)button.onclick=()=>{
    const target=button.dataset.alpineView;
    const item=route();
    if(target==='zone'||!item)showView(alpine.view(zone().point));
    else if(target==='start')showView(alpine.view(item.points[0],145));
    else if(target==='end')showView(alpine.view(item.points.at(-1),145));
    else{
      const a=item.points[0],b=item.points.at(-1);
      const centre=[(a[0]+b[0])*.5,(a[1]+b[1])*.5];
      showView(alpine.view(centre,Math.min(3200,Math.max(260,item.distance*.7))));
    }
    dialog.close();
  };
  return {
    setWorld(next) {
      alpine=next;trigger.hidden=!next;
      if(dialog.open)dialog.close();
      if(!next)return;
      zoneSelect.replaceChildren(...next.zones.map(item=>option(`${item.name} · ${item.area}`,item.id)));
      chooseZone();
    },
  };
}
