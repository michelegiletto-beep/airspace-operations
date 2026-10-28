import {describe,expect,it} from 'vitest';
import {asGeometry,boundsForPoints,geometryCoordinates,pathForGeometry,projection} from './geometry';
describe('display geometry boundary',()=>{
 it('keeps malformed, out-of-range and missing coordinates absent',()=>{expect(asGeometry(undefined)).toBeNull();expect(asGeometry('not-json')).toBeNull();expect(geometryCoordinates({type:'Point',coordinates:[500,95]})).toEqual([]);expect(geometryCoordinates({type:'Point',coordinates:[6.1,49.6]})).toEqual([[6.1,49.6]]);});
 it('round-trips explicit WGS 84 coordinates in the visual projection without a safety-distance calculation',()=>{const {project,unproject}=projection([-10,35,30,60],1000,600);const point:[number,number]=[6.1,49.6];const result=unproject(project(point));expect(result[0]).toBeCloseTo(point[0],8);expect(result[1]).toBeCloseTo(point[1],8);});
 it('separates a GeoJSON feature from its geometry and fits supplied points',()=>{const geometry={type:'LineString',coordinates:[[6,49],[7,50]]};expect(asGeometry({type:'Feature',geometry,properties:{title:'Isolated geometry test'}})).toEqual(geometry);expect(boundsForPoints([[6,49],[7,50]])).toEqual([5.8,48.8,7.2,50.2]);expect(pathForGeometry(geometry,point=>point)).toBe('M6.00,49.00 L7.00,50.00');});
 it('does not coerce text into a reported position',()=>{expect(geometryCoordinates({type:'Point',coordinates:['6.1','49.6']})).toEqual([]);});
});
