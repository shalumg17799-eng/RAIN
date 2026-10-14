// Adds the 3 missing Risk Signal mappings, found via Sarah's cache-
// validation test: the live pipeline correctly refused to answer
// medication-gap, overdue-A1c, and lost-provider questions because these
// tables were never mapped to the concept, even though real, tested
// business rules for them already exist. Real gaps, not invented.
//
// Safe to run on your already-cleaned graph -- only touches RAIN content,
// doesn't reintroduce USSFCU.

MERGE (f1:SourceField {name: 'fill_date', source_system: 'MedicationFill'})
MERGE (s1:SourceSystem {name: 'MedicationFill'})
MERGE (f1)-[:BELONGS_TO]->(s1);
MATCH (c:Concept {concept_id: 'C-RISK-SIGNAL'}), (f1:SourceField {name: 'fill_date', source_system: 'MedicationFill'})
MERGE (c)-[r1:MAPS_TO]->(f1)
SET r1.domain = 'RAIN', r1.confidence_category = 'auto-eligible',
    r1.note = 'added after live-SQL testing on Sarah persona -- medication-gap questions genuinely need this table';

MERGE (f2:SourceField {name: 'condition_type', source_system: 'ChronicConditionEnrollment'})
MERGE (s2:SourceSystem {name: 'ChronicConditionEnrollment'})
MERGE (f2)-[:BELONGS_TO]->(s2);
MATCH (c:Concept {concept_id: 'C-RISK-SIGNAL'}), (f2:SourceField {name: 'condition_type', source_system: 'ChronicConditionEnrollment'})
MERGE (c)-[r2:MAPS_TO]->(f2)
SET r2.domain = 'RAIN', r2.confidence_category = 'auto-eligible',
    r2.note = 'added after live-SQL testing -- overdue-care-gap questions genuinely need this table';

MERGE (f3:SourceField {name: 'status', source_system: 'Provider'})
MERGE (s3:SourceSystem {name: 'Provider'})
MERGE (f3)-[:BELONGS_TO]->(s3);
MATCH (c:Concept {concept_id: 'C-RISK-SIGNAL'}), (f3:SourceField {name: 'status', source_system: 'Provider'})
MERGE (c)-[r3:MAPS_TO]->(f3)
SET r3.domain = 'RAIN', r3.confidence_category = 'auto-eligible',
    r3.note = 'added after live-SQL testing -- lost-provider-continuity questions genuinely need this table';
