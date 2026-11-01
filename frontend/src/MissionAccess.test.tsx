import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {MissionDesk} from './MissionDesk';
import type {User} from './api';

vi.mock('./workspaceData',()=>({useWorkspaceData:()=>({records:{},loading:false,error:'',checkedAt:''})}));
vi.mock('./AirspaceMap',()=>({AirspaceMap:()=>null}));
vi.mock('./AgentCompanion',()=>({AgentCompanion:()=>null}));
afterEach(()=>{cleanup();sessionStorage.clear();vi.unstubAllGlobals();});
const base:User={id:'isolated-actor',email:'role@test.invalid',role:'regulatory',organisation_id:'isolated-org'};

describe('mission planning role guidance',()=>{
 it.each(['regulatory','administrator','reviewer','fleet_manager','incident_coordinator','analyst','viewer'])('explains the %s boundary without opening a draft or sending data',role=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);const navigate=vi.fn();
  render(<MissionDesk token="isolated-token" user={{...base,role}} revision={0} changed={()=>undefined} navigate={navigate}/>);
  const note=screen.getByText(`Your ${role} role can inspect mission records. Creating a mission proposal requires the planner or pilot role.`);
  for(const name of ['Plan a mission','Create mission proposal']){
   const button=screen.getByRole('button',{name}) as HTMLButtonElement;
   expect(button.disabled).toBe(true);
   expect(button.getAttribute('aria-describedby')).toBe(note.id);
   fireEvent.click(button);
  }
  expect(screen.queryByRole('heading',{name:'Plan an intended mission'})).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Review authorisation cases'}));
  expect(navigate).toHaveBeenCalledWith('authorisations');
 });
 it.each(['planner','pilot'])('retains the %s draft form with unassigned resources',role=>{
  render(<MissionDesk token="isolated-token" user={{...base,role}} revision={0} changed={()=>undefined} navigate={()=>undefined}/>);
  expect(screen.queryByText(/Creating a mission proposal requires/)).toBeNull();
  expect((screen.getByRole('button',{name:'Plan a mission'}) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Create mission proposal'}));
  expect(screen.getByRole('heading',{name:'Plan an intended mission'})).toBeTruthy();
  expect((screen.getByLabelText('Aircraft configuration') as HTMLSelectElement).value).toBe('');
  expect((screen.getByLabelText('Route') as HTMLSelectElement).value).toBe('');
 });
});
