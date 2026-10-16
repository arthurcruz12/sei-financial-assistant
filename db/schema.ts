// Intentionally empty by default.
// Add Drizzle tables here when the site actually needs a database.
// See examples/d1/db/schema.ts for an opt-in example.
import { sqliteTable, text, primaryKey } from 'drizzle-orm/sqlite-core';
export const records = sqliteTable('records', {
  owner: text('owner').notNull(),
  kind: text('kind').notNull(),
  id: text('id').notNull(),
  body: text('body').notNull(),
  updated: text('updated').notNull(),
}, t => [primaryKey({columns:[t.owner,t.kind,t.id]})]);
