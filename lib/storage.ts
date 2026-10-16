import {env} from 'cloudflare:workers';
export function database(){const db=(env as unknown as {DB?:D1Database}).DB;if(!db)throw Error('Armazenamento indisponível');return db;}
export function owner(request:Request){return request.headers.get('oai-authenticated-user-id');}
export function sameOrigin(request:Request){const origin=request.headers.get('origin');return !origin||origin===new URL(request.url).origin;}
