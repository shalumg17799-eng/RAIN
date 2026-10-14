// Adds the missing Access Barrier -> TransportRequest mapping, found via
// the cache-validation test: the live pipeline correctly refused to
// answer transport-scheduling questions because this table was never
// mapped to the concept, even though the real column (scheduled) is
// exactly what those questions need. Real gap, not invented.
//
// Safe to run on your already-cleaned graph -- only touches RAIN content,
// doesn't reintroduce USSFCU.

MERGE (s:SourceSystem {name: 'TransportRequest'})
MERGE (f:SourceField {name: 'scheduled', source_system: 'TransportRequest'})
MERGE (f)-[:BELONGS_TO]->(s);

MATCH (c:Concept {concept_id: 'C-ACCESS-BARRIER'}), (f:SourceField {name: 'scheduled', source_system: 'TransportRequest'})
MERGE (c)-[r:MAPS_TO]->(f)
SET r.domain = 'RAIN', r.confidence_category = 'auto-eligible',
    r.note = 'added after live-SQL testing showed transport-scheduling questions genuinely need this table';
