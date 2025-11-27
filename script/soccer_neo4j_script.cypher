// -----------------------------
// 1. Delete EVERYTHING (reset DB)
// -----------------------------
MATCH (n)
DETACH DELETE n;

// -----------------------------
// 2. Create Constraints
// -----------------------------
CREATE CONSTRAINT player_id_unique IF NOT EXISTS
FOR (p:Player)
REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT club_name_unique IF NOT EXISTS
FOR (c:Club)
REQUIRE c.name IS UNIQUE;

// -----------------------------
// 3. Load save.csv Into Graph
// -----------------------------
LOAD CSV WITH HEADERS FROM "https://media.githubusercontent.com/media/joopixel1/SportGraph/refs/heads/main/data/save.csv" AS row

WITH row
WHERE
  row.club IS NOT NULL AND
  row.club <> "" AND
  row.player_id IS NOT NULL AND
  row.player_id <> "" AND
  row.player_name IS NOT NULL AND
  row.player_name <> ""

WITH
  row,
  toInteger(
    CASE
      WHEN row.start CONTAINS "-" THEN split(row.start, "-")[0]
      ELSE row.start
    END) AS rs,
  toInteger(
    CASE
      WHEN row.end CONTAINS "-" THEN split(row.end, "-")[1]
      ELSE row.end
    END) AS re,
  toInteger(row.appearances) AS apps

MERGE (p:Player {id: row.player_id})
SET p.name = row.player_name

MERGE (c:Club {name: row.club})

MERGE (p)-[r:PLAYED_FOR]->(c)
SET
  r.start_raw = row.start,
  r.end_raw = row.end,
  r.apps_raw = row.appearances,
  r.start_year = rs,
  r.end_year = re,
  r.appearances = apps;

// -----------------------------
// 4. View 1000 Relationships
// -----------------------------
MATCH p = ()-[]->()
RETURN p
LIMIT 1000;

// -----------------------------
// 5. Create PLAYED_WITH Relationships
// -----------------------------
MATCH (p1:Player)-[r1:PLAYED_FOR]->(c:Club)<-[r2:PLAYED_FOR]-(p2:Player)
WHERE
  p1.id < p2.id AND
  r1.start_year <= r2.end_year AND
  r2.start_year <= r1.end_year

WITH
  p1,
  p2,
  c,
  apoc.coll.max([r1.start_year, r2.start_year]) AS overlap_start,
  apoc.coll.min([r1.end_year, r2.end_year]) AS overlap_end,
  r1.appearances + r2.appearances AS weight

WHERE overlap_start <= overlap_end

MERGE (p1)-[pw:PLAYED_WITH]->(p2)
SET
  pw.club = c.name,
  pw.start = overlap_start,
  pw.end = overlap_end,
  pw.seasons_overlap = overlap_end - overlap_start + 1,
  pw.weight = weight;