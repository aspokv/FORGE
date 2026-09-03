import {prescribedReps} from './prescribedReps';
test('pyramid target follows the current set',()=>{
  expect([0,1,2,3].map(i=>prescribedReps('12/10/8/6',i))).toEqual(['12','10','8','6']);
});
test('ranges and drops never enter invalid strings into numeric fields',()=>{
  expect(prescribedReps('8–12')).toBe('8');
  expect(prescribedReps('10+10+10')).toBe('10');
  expect(prescribedReps('12/12/falha técnica',2)).toBe('');
});
