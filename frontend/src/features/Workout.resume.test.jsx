import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import {Workout} from '../App';
import {resumeStorageKey} from './workoutResume';
jest.mock('axios',()=>({get:jest.fn(),put:jest.fn(),post:jest.fn()}));
jest.mock('./AuthContext',()=>({AuthProvider:({children})=>children,useAuth:()=>({user:{}})}));
jest.mock('./workoutCalendar',()=>({useScheduledProgram:p=>p}));
let mockCompletion=null;
jest.mock('./workoutCompletionState',()=>({useWorkoutCompletion:()=>({completion:mockCompletion,status:'ready'})}));
jest.mock('./MuscleSessionMap',()=>()=>null);
jest.mock('./ObservacaoDoExercicio',()=>()=>null);
global.IS_REACT_ACT_ENVIRONMENT=true;
const db={current_user:{id:'resume-user'},profile:{id:'resume-user'},exercises:[{id:'row',name:'Remada'}],recent_sets:[],program:{active_day:1,week:'Week 1',sessions:[{day:1,label:'Session',exercises:[{exercise_id:'row',sets:2,reps:'8',rir:2,rest:'90',load:20}]}]}};
let host,root;
beforeEach(()=>{localStorage.clear();mockCompletion=null;axios.get.mockReset();axios.post.mockReset();axios.get.mockResolvedValue({data:{}});axios.put.mockResolvedValue({data:{}});axios.post.mockResolvedValue({data:{}});host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();});
const mount=()=>act(async()=>root.render(<Workout db={db} techniques={[]}/>));
const click=selector=>act(async()=>host.querySelector(selector).click());
test('remount returns to the live workout and confirmed sets, without new POSTs',async()=>{
 await mount();await click('[data-testid="workout-preview-start"]');
 await click('[data-testid="complete-set-row-1"]');
 const posts=axios.post.mock.calls.length;
 await act(async()=>root.unmount());root=createRoot(host);await mount();
 expect(host.querySelector('[data-testid="workout-resumable-session"]')).not.toBeNull();
 expect(host.querySelector('[data-testid="complete-set-row-1"]').getAttribute('aria-label')).toContain('concluída');
 expect(axios.post).toHaveBeenCalledTimes(posts);
});
test('an unconfirmed POST is not restored as a saved set',async()=>{
 axios.post.mockImplementation(()=>new Promise(()=>{}));
 await mount();await click('[data-testid="workout-preview-start"]');await click('[data-testid="complete-set-row-1"]');
 expect(JSON.parse(localStorage.getItem(resumeStorageKey('resume-user'))).done).toEqual({});
});
test('a completed workout clears its resume record and cannot restart',async()=>{
 await mount();await click('[data-testid="workout-preview-start"]');
 mockCompletion={completed_at:new Date().toISOString(),day:1,label:'Session'};await mount();
 expect(host.querySelector('[data-testid="workout-resumable-session"]')).toBeNull();
 expect(localStorage.getItem(resumeStorageKey('resume-user'))).toBeNull();
});
test('reopening retains typed loads even when the server draft is unavailable',async()=>{
 await mount();await click('[data-testid="workout-preview-start"]');
 await act(async()=>{const input=host.querySelector('[data-testid="weight-row-2"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'35');input.dispatchEvent(new Event('input',{bubbles:true}));window.dispatchEvent(new Event('pagehide'));});
 await act(async()=>root.unmount());root=createRoot(host);await mount();
 expect(host.querySelector('[data-testid="weight-row-2"]').value).toBe('35');
});
test('a late set response cannot recreate a completed session',async()=>{
 let resolvePost;axios.post.mockImplementation(()=>new Promise(resolve=>{resolvePost=resolve;}));
 await mount();await click('[data-testid="workout-preview-start"]');await click('[data-testid="complete-set-row-1"]');
 mockCompletion={completed_at:new Date().toISOString(),day:1,label:'Session'};await mount();
 await act(async()=>resolvePost({data:{}}));
 expect(localStorage.getItem(resumeStorageKey('resume-user'))).toBeNull();
 expect(host.querySelector('[data-testid="workout-resumable-session"]')).toBeNull();
});
