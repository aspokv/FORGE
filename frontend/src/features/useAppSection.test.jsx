import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import useAppSection from './useAppSection';
import {resumeDate} from './workoutResume';
global.IS_REACT_ACT_ENVIRONMENT=true;
let host,root;
function Navigation({user='athlete'}){const [section,navigate]=useAppSection(user);return <><p>{section}</p><button onClick={()=>navigate('Treino')}>Treino</button></>;}
const mount=user=>act(async()=>root.render(<Navigation user={user}/>));
beforeEach(()=>{localStorage.clear();window.history.replaceState({},'','/app');host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();window.history.replaceState({},'','/');});
test('fresh browser entry restores the last training tab for the same user today',async()=>{
 await mount();await act(async()=>host.querySelector('button').click());
 await act(async()=>root.unmount());root=createRoot(host);window.history.replaceState({},'','/app');await mount();
 expect(host.querySelector('p').textContent).toBe('Treino');
});
test.each([['different-user',resumeDate(),'other'],['stale-day','2000-01-01','athlete']])('%s does not reuse another session',async(_,date,user)=>{
 localStorage.setItem('forge_last_section:athlete',JSON.stringify({date,section:'Treino'}));await mount(user);
 expect(host.querySelector('p').textContent).toBe('Hoje');
});
test('an explicit destination takes precedence over the saved tab',async()=>{
 localStorage.setItem('forge_last_section:athlete',JSON.stringify({date:resumeDate(),section:'Treino'}));
 window.history.replaceState({},'','/app?view=nutricao');await mount();
 expect(host.querySelector('p').textContent).toBe('Alimentação');
});
