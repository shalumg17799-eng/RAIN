// Adds Facility -- the one remaining table with a clear, defensible
// concept home already: closure_date directly ties to the Battle
// Mountain ClosureEvent already in the graph, and facility_id is
// referenced by PregnancyEpisode.delivering_facility_id (real,
// distance-to-care access story). Mapped to Access Barrier.
//
// Safe to run on your graph -- RAIN-only, no USSFCU content touched.

MERGE (s:SourceSystem {name: 'Facility'})
MERGE (f:SourceField {name: 'closure_date', source_system: 'Facility'})
MERGE (f)-[:BELONGS_TO]->(s);

MATCH (c:Concept {concept_id: 'C-ACCESS-BARRIER'}), (f:SourceField {name: 'closure_date', source_system: 'Facility'})
MERGE (c)-[r:MAPS_TO]->(f)
SET r.domain = 'RAIN', r.confidence_category = 'auto-eligible',
    r.note = 'Facility.closure_date directly represents the structural access event (Battle Mountain closure) already tracked as ClosureEvent';
