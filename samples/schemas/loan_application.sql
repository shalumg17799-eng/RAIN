-- source: core_banking
CREATE TABLE loan_application (
  id BIGINT PRIMARY KEY,
  member_id BIGINT NOT NULL REFERENCES member(id),
  product_type VARCHAR(40) NOT NULL,
  status VARCHAR(20) NOT NULL,
  amount NUMERIC(12,2),
  applied_at TIMESTAMP
);
