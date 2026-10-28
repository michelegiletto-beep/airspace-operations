export type Coordinate = [number, number];
export interface Geometry { type: string; coordinates: unknown }
export interface MapFeature { type: 'Feature'; properties: { id: string; name: string; iso_a2?: string; label?: Coordinate }; geometry: Geometry }
export interface FeatureCollection { type: 'FeatureCollection'; features: MapFeature[] }
export function asGeometry(input: unknown): Geometry | null {
 try { const value: unknown = typeof input === 'string' ? JSON.parse(input) : input;
  if (!value || typeof value !== 'object') return null;
  if ('type' in value && value.type === 'Feature' && 'geometry' in value) return asGeometry(value.geometry);
  if ('type' in value && typeof value.type === 'string' && ['Point','LineString','Polygon','MultiPolygon','MultiLineString','MultiPoint'].includes(value.type) && 'coordinates' in value) return { type: value.type, coordinates: value.coordinates };
 } catch { /* A malformed geometry is missing coverage, never a position. */ }
 return null;
}
export function coordinates(input: unknown, limit = 20000): Coordinate[] {
 const output: Coordinate[] = [];
 function visit(value: unknown, depth: number) {
  if (!Array.isArray(value) || depth > 6 || output.length >= limit) return;
  if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
   if (Number.isFinite(value[0]) && Number.isFinite(value[1]) && value[0] >= -180 && value[0] <= 180 && value[1] >= -90 && value[1] <= 90) output.push([value[0], value[1]]);
  } else for (const child of value) visit(child, depth + 1);
 }
 visit(input, 0); return output;
}
export function geometryCoordinates(input: unknown): Coordinate[] { const geometry = asGeometry(input); return geometry ? coordinates(geometry.coordinates) : []; }
export type Bounds = [number, number, number, number];
export const europeBounds: Bounds = [-8.5, 36, 27, 57];
export function mercatorY(latitude: number): number { return Math.log(Math.tan(Math.PI / 4 + Math.max(-84, Math.min(84, latitude)) * Math.PI / 360)) * 180 / Math.PI; }
export function unprojectY(value: number): number { return (2 * Math.atan(Math.exp(value * Math.PI / 180)) - Math.PI / 2) * 180 / Math.PI; }
export function projection(bounds: Bounds, width: number, height: number) {
 const [west,south,east,north] = bounds; const bottom = mercatorY(south), top = mercatorY(north);
 const scale = Math.min(width / (east - west), height / (top - bottom));
 const left = (width - (east - west) * scale) / 2, above = (height - (top - bottom) * scale) / 2;
 return {
  project: ([longitude, latitude]: Coordinate): Coordinate => [left + (longitude - west) * scale, above + (top - mercatorY(latitude)) * scale],
  unproject: ([x,y]: Coordinate): Coordinate => [west + (x - left) / scale, unprojectY(top - (y - above) / scale)],
 };
}
export function pathForGeometry(geometry: Geometry, project: (point: Coordinate) => Coordinate): string {
 function ring(raw: unknown, closed = false): string { const points = coordinates(raw); if (!points.length) return ''; return points.map((point,index) => { const [x,y] = project(point); return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`; }).join(' ') + (closed ? ' Z' : ''); }
 if (geometry.type === 'LineString') return ring(geometry.coordinates);
 if (geometry.type === 'MultiLineString') return (geometry.coordinates as unknown[]).map(part => ring(part)).join(' ');
 if (geometry.type === 'Polygon') return (geometry.coordinates as unknown[]).map(part => ring(part,true)).join(' ');
 if (geometry.type === 'MultiPolygon') return (geometry.coordinates as unknown[][]).flatMap(polygon => polygon.map(part => ring(part,true))).join(' ');
 return '';
}
export function boundsForPoints(points: Coordinate[]): Bounds {
 if (!points.length) return europeBounds;
 let west=180,east=-180,south=90,north=-90;
 for(const point of points){west=Math.min(west,point[0]);east=Math.max(east,point[0]);south=Math.min(south,point[1]);north=Math.max(north,point[1]);}
 const px = Math.max((east - west) * .2, .08), py = Math.max((north - south) * .2, .08);
 return [Math.max(-179,west-px),Math.max(-83,south-py),Math.min(179,east+px),Math.min(83,north+py)];
}
