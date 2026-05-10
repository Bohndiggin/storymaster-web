// Hand-written for now; switch to `openapi-typescript` codegen against
// /openapi.json once the API is locked. The shapes here mirror the Pydantic
// DTOs in storymaster/api/schemas/*.

export interface User {
  id: number;
  username: string;
  is_active: boolean;
}

export interface Timestamped {
  sync_uuid: string;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface Storyline extends Timestamped {
  id: number;
  name: string | null;
  description: string | null;
  user_id: number;
}

export interface Setting extends Timestamped {
  id: number;
  name: string | null;
  description: string | null;
  user_id: number;
}

export type NodeType =
  | "exposition"
  | "action"
  | "reaction"
  | "twist"
  | "development"
  | "other";

export interface LitographyNode extends Timestamped {
  id: number;
  name: string;
  description: string | null;
  node_type: NodeType;
  x_position: number;
  y_position: number;
  storyline_id: number;
}

export interface NodeConnection extends Timestamped {
  id: number;
  output_node_id: number;
  input_node_id: number;
}

export interface LorekeeperColumn {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
  foreign_key?: { table: string; column: string };
}

export interface LorekeeperTable {
  columns: LorekeeperColumn[];
}

export interface LorekeeperSchema {
  tables: Record<string, LorekeeperTable>;
}

export interface EntityIndexItem {
  entity_type: string;
  id: number;
  name: string;
}

export interface ArcType extends Timestamped {
  id: number;
  name: string;
  description: string | null;
  setting_id: number;
}

export interface Arc extends Timestamped {
  id: number;
  title: string;
  description: string | null;
  arc_type_id: number;
  storyline_id: number;
}

export interface ArcPoint extends Timestamped {
  id: number;
  arc_id: number;
  title: string;
  order_index: number;
  description: string | null;
  emotional_state: string | null;
  character_relationships: string | null;
  goals: string | null;
  internal_conflict: string | null;
  node_id: number | null;
}

// The generic entity rows are dynamic — every table has a different column
// set. Callers that need a typed shape should narrow this manually.
export type EntityRow = Record<string, unknown> & { id: number; setting_id?: number };
