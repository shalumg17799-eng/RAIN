CREATE TABLE fair_lending_snapshot (
  snapshot_id BIGINT PRIMARY KEY,
  loan_application_id BIGINT,
  approval_rate NUMERIC(5,4),
  snapshot_date DATE
);
