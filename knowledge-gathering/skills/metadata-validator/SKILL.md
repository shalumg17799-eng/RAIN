---
name: metadata-validator
version: 1.0.0
description: Validates a metadata graph for completeness, relationship integrity and lineage coverage; returns issues and a 0-1 confidence score.
dependencies: [schema-metadata-extractor]
validation:
  required_input: [extraction]
  required_output: [valid, confidence, checks, issues]
---

# Metadata Validator

Checks: **completeness** (every table has columns and a primary key), **relationships** (every foreign key points to a
known table/column), **lineage** (every table has a source system). Confidence = weighted pass ratio of checks.
