-- source: crm
CREATE TABLE member (
  id BIGINT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  zip_code VARCHAR(10),
  joined_at DATE
);
