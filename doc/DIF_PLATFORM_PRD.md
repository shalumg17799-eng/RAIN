Below is a consolidated deliverable containing:

Complete User Story Backlog
PRD for Santosh's P1 Assignment
Markdown (.md) content ready to save as:
DataFactory-Agentic-Platform-P1-PRD.md
DataFactory-Agentic-Platform-Backlog.md
Data Factory Agentic Platform
Product Requirements Document (PRD)
1. Executive Summary

The Data Factory Agentic Platform aims to automate the generation of enterprise knowledge assets by converting business and technical artifacts into structured metadata, enriched domain models, ontologies, and Knowledge Asset Graphs (KAG).

The platform will initially be developed using a fully Open Source/FOSS stack to accelerate development, minimize cost, and avoid cloud lock-in.

Once Azure environments become available, the platform will transition through adapter-based migration without impacting agent logic, skills, metadata models, or workflows.

2. Objectives
Phase 1 (Current)

Build:

Agent Runtime Framework
Skill Framework
Metadata Extraction Agent
Agent Registry
Evaluation Framework

using OSS technologies.

Phase 2 (Future)

Migrate infrastructure to Azure:

Azure Container Apps
Azure OpenAI
Azure PostgreSQL
Azure Redis
Azure AI Search
Azure Monitor

without changing agent implementations.

3. Scope
In Scope
Agent Platform
Agent Runtime
Skill Loader
Skill Registry
Workflow Engine
Metadata Factory
Schema Metadata Extraction
Metadata Normalization
Domain Enrichment
Ontology Generation
Knowledge Factory
KAG Population
Knowledge Graph Integration
Out of Scope
Production Azure deployment
Enterprise SSO
Multi-region DR
Fine-grained RBAC
4. Architecture Vision
+------------------------------------------------+
|            Agent Runtime Layer                 |
+------------------------------------------------+
|                  Agents                        |
+------------------------------------------------+
|                   Skills                        |
+------------------------------------------------+
| Workflow Engine / LangGraph                    |
+------------------------------------------------+
| PostgreSQL | Neo4j | Qdrant                    |
+------------------------------------------------+
| Docker Compose Infrastructure                  |
+------------------------------------------------+

5. Open Source Technology Stack
Runtime
Python
FastAPI
LangGraph

Agent Storage
PostgreSQL

Knowledge Graph
Neo4j Community

Vector DB
Qdrant

Cache / Queue
Redis

Deployment
Docker
Docker Compose

Monitoring
Prometheus
Grafana
OpenTelemetry

Local Models
Ollama
Llama
Mistral

6. Azure Migration Strategy
OSS Component	Azure MigrationDocker Compose	Azure Container Apps
PostgreSQL	Azure Database for PostgreSQL
Redis	Azure Redis
Qdrant	Azure AI Search
Ollama	Azure OpenAI
Grafana	Azure Monitor

Migration accomplished through configuration changes.

No skill or agent modifications required.

7. Skill-Based Framework

Each capability must be implemented as a Skill.

Example:

skills/
  schema-metadata-extractor/
      SKILL.md
      scripts/
      assets/

  domain-model-enricher/
      SKILL.md
      scripts/

  ontology-builder/
      SKILL.md
      scripts/

8. Metadata Extraction Business Flow
PRD
Schema
Source Metadata
      |
      v
Metadata Extraction Agent
      |
      v
Normalized Metadata Graph
      |
      v
Domain Enrichment Agent
      |
      v
Lower Ontology Agent
      |
      v
Upper Ontology Agent
      |
      v
KAG Repository

9. Sample Metadata Extraction
Input
{
  "prd":"USSFCU Compliance Dashboard PRD",
  "schemas":[
      "loan_application",
      "member",
      "fair_lending_snapshot"
  ]
}

Internal Processing

Skill performs:

Entity Discovery
Table Discovery
Column Discovery
Key Detection
Lineage Detection
Output
{
  "tables":[
     "loan_application",
     "member"
  ],
  "columns":{
      "loan_application":[
          "id",
          "product_type",
          "status"
      ]
  },
  "lineage":{
     "loan_application":"core_banking"
  }
}

Sprint-1 Objective 

Build foundational platform components necessary for downstream agents.

Success Criteria:

Runtime operational
Skills executable
Metadata Extraction POC complete
Registry operational
Evaluation framework available
Product Backlog
EPIC DF-001
Agent Runtime Framework
US-001
Build Agent Runtime Engine

As a Platform Engineer

I want a generic runtime engine

So that agents can execute across environments.

Acceptance Criteria

Agent execution supported
Agent lifecycle management available
Logging enabled
Configuration-driven deployment
US-002
Runtime State Management

As a Platform Engineer

I want runtime state persistence

So that workflows are recoverable.

Acceptance Criteria

Persist state
Resume execution
Audit execution history
US-003
Agent Monitoring Framework

Acceptance Criteria

Agent metrics
Runtime metrics
Execution dashboards
EPIC DF-002
Skill Framework
US-004
Build Skill Registry

As a Developer

I want skills discovered dynamically

So that agents do not require code changes.

Acceptance Criteria

Register skill
Load skill
Execute skill
Version skill
US-005
SKILL.md Framework

Acceptance Criteria

Skill metadata
Dependencies
Examples
Validation rules
US-006
Evaluation Framework

Acceptance Criteria

Dry Run Mode
Test Execution
Confidence Scoring
Validation Reports
EPIC DF-003
Metadata Extraction Factory
US-007
Schema Metadata Extraction Skill

Input

{
  "prd":"PRD document",
  "schemas":[]
}


Internal Process

Read schema
Read PRD
Discover entities
Discover columns
Detect lineage

Output

{
  "metadata_graph":{}
}


Artifact

Normalized Metadata Graph

US-008
Metadata Extraction Agent

Acceptance Criteria

Execute Metadata Skill
Generate Metadata Graph
Persist Results
US-009
Metadata Validation Skill

Acceptance Criteria

Check completeness
Check relationships
Validate lineage
EPIC DF-004
Domain Enrichment Factory
US-010
Domain Enricher Skill

Input

Metadata Graph

Internal Process

Capability Mapping
Domain Identification
Taxonomy Mapping

Output

{
   "domain":"Lending",
   "capability":"Loan Origination"
}

US-011
Domain Enrichment Agent

Acceptance Criteria

Load Domain Skill
Enrich Metadata
Generate Domain Catalog
EPIC DF-005
Ontology Factory
US-012
Lower Ontology Skill

Acceptance Criteria

Generate:

Entity
Attribute
Relationship

Models.

US-013
Upper Ontology Skill

Acceptance Criteria

Generate:

Business Concepts
Enterprise Model
Knowledge Relationships
EPIC DF-006
Knowledge Graph Factory
US-014
Neo4j Publishing Skill

Acceptance Criteria

Create Nodes
Create Relationships
Create Lineage
US-015
KAG Publishing Agent

Acceptance Criteria

Publish ontology
Publish metadata graph
Support versioning
Santosh P1 Sprint Backlog
Sprint Goal

Deliver the foundational Agentic Platform required by all downstream factories.

Story 1

Build Agent Runtime Engine

Priority: P1

Estimated: 5 Days

Story 2

Build Skill Registry

Priority: P1

Estimated: 3 Days

Story 3

Implement SKILL.md Framework

Priority: P1

Estimated: 2 Days

Story 4

Build Schema Metadata Extractor Skill

Priority: P1

Estimated: 5 Days

Story 5

Build Metadata Extraction Agent

Priority: P1

Estimated: 3 Days

Story 6

Build Evaluation Framework

Priority: P1

Estimated: 2 Days

Story 7

Create OSS-to-Azure Migration Architecture

Priority: P1

Estimated: 1 Day

Expected Sprint Deliverables
✓ Agent Runtime Framework

✓ Skill Registry

✓ SKILL.md Specification

✓ Metadata Extraction Agent

✓ Metadata Extraction Skill

✓ Evaluation Framework

✓ OSS Deployment Architecture

✓ Azure Migration Blueprint

✓ POC Demonstration

✓ Technical Documentation


