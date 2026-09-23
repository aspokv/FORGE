import {workoutResumeContext,readWorkoutResume,saveWorkoutResume,clearWorkoutResume,resumeStorageKey} from './workoutResume';
const items=[{exercise_id:'row',sets:3,reps:'8'}],session={day:1,label:'Session'},program={week:'Week 1'};
const context=(user='u',date='2026-09-22',list=items)=>workoutResumeContext(user,program,session,list,date);
beforeEach(()=>localStorage.clear());
test('resumes only the same user, day and unchanged session',()=>{
 saveWorkoutResume('u',context(),{started:true,startedAt:123,done:{row0:true},inputs:{'row-0':{weight:20}},anchor:'row'});
 expect(readWorkoutResume('u',context()).done).toEqual({row0:true});
 expect(readWorkoutResume('v',context('v'))).toBeNull();
 expect(readWorkoutResume('u',context('u','2026-09-23'))).toBeNull();
 expect(readWorkoutResume('u',context('u','2026-09-22',[{...items[0],sets:4}]))).toBeNull();
 clearWorkoutResume('u');expect(readWorkoutResume('u',context())).toBeNull();
});
test('confirmed server rows recover an interrupted response without posting them again',()=>{
 saveWorkoutResume('u',context(),{started:true,startedAt:123,done:{},inputs:{}});
 const r=readWorkoutResume('u',context(),[
 {exercise_id:'row',session_day:1,set_number:1,created_at:'2026-09-22T12:00:00Z',weight:25,reps:8,rir:2},
 {exercise_id:'row',session_day:2,set_number:2,created_at:'2026-09-22T12:00:00Z'},
 {exercise_id:'row',session_day:1,set_number:3,created_at:'2026-09-21T12:00:00Z'}]);
 expect(r.done).toEqual({row0:true});expect(r.inputs['row-0'].weight).toBe(25);
});
test('malformed storage and rest days do not start a workout',()=>{
 localStorage.setItem(resumeStorageKey('u'),'bad json');expect(readWorkoutResume('u',context())).toBeNull();
 expect(workoutResumeContext('u',{rest_day:true},session,items)).toBeNull();
});
