import {catalog,fetchSeries} from '../../../lib/economics';
export async function GET(){const series=await Promise.all(catalog.map(fetchSeries));return Response.json({series,fetchedAt:new Date().toISOString()},{headers:{'Cache-Control':'private, max-age=300'}});}
