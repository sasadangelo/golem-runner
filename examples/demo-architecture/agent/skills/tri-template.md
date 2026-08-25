[//]: # (Template Version 0.5.1)
# {{SERVICE_NAME}} Technical Requirements Interlock (TRI)

## Version Control and Ownership

**Technical Requirements Interlock Project Management Owner:** {{PM_OWNER_NAME}}

**Technical Requirements Interlock Development Owner:** {{DEV_OWNER_NAME}}

---

### TRI Team

#### Approvers

| Team | Name | Email |
|:-----|:-----|:------|
| {{TEAM}} | {{APPROVER_NAME}} | {{APPROVER_EMAIL}} |

#### Reviewers

| Team | Name | Email |
|:-----|:-----|:------|
| {{TEAM}} | {{REVIEWER_NAME}} | {{REVIEWER_EMAIL}} |

---

## Service Introduction and Goals

### Service Description

{{SERVICE_DESCRIPTION}}

### New Concepts and Terms

{{NEW_CONCEPTS}}

### Assumptions

{{ASSUMPTIONS}}

### Success Metrics and Exit Criteria

{{SUCCESS_METRICS}}

---

## High Level Architecture

### Architecture Diagram

[Architecture diagram to be added by the service team — preferred format: Draw.io]

### Technical Design

{{TECHNICAL_DESIGN}}

### Trust Zones

| Name | Description | Boundary | Physical location |
|------|-------------|----------|-------------------|
| {{ZONE_NAME}} | {{ZONE_DESCRIPTION}} | {{ZONE_BOUNDARY}} | {{ZONE_LOCATION}} |

### Interfaces / Endpoints (APIs and UIs)

| Name | Type | Description | Exposed to zones | Authentication | Justification - Public exposure |
|------|------|-------------|------------------|----------------|----------------------------------|
| {{ENDPOINT_NAME}} | {{ENDPOINT_TYPE}} | {{ENDPOINT_DESCRIPTION}} | {{EXPOSED_TO}} | {{AUTH_METHOD}} | {{JUSTIFICATION}} |

### Data Flows

| Source Zone | Destination Zone | Data Description | Protocol/Ports | Encryption | Authentication method | Classification | Scope |
|-------------|-----------------|-----------------|----------------|------------|-----------------------|---------------|-------|
| {{SOURCE}} | {{DESTINATION}} | {{DATA_DESC}} | {{PROTOCOL}} | {{ENCRYPTION}} | {{AUTH}} | {{CLASSIFICATION}} | {{SCOPE}} |

### Datastores

| Data Store | Data | Encryption | Storage of encryption key | Ownership on encryption key | Classification | Trust Zone | Zones with network access | Access control | Auth method | Who has access |
|-----------|------|-----------|--------------------------|----------------------------|---------------|------------|--------------------------|---------------|------------|----------------|
| {{STORE_NAME}} | {{DATA}} | {{ENCRYPTION}} | {{KEY_STORAGE}} | {{KEY_OWNERSHIP}} | {{CLASSIFICATION}} | {{TRUST_ZONE}} | {{NETWORK_ACCESS}} | {{ACCESS_CONTROL}} | {{AUTH_METHOD}} | {{WHO_HAS_ACCESS}} |

### Service Dependencies

| External Dependency | Brief Description | Client Owned Data | Encrypted | CSRM Entry Link | CSRM Approval State |
|---------------------|------------------|-------------------|-----------|-----------------|---------------------|
| {{DEPENDENCY}} | {{DESCRIPTION}} | {{CLIENT_DATA}} | {{ENCRYPTED}} | {{CSRM_LINK}} | {{CSRM_STATE}} |

### Components / Processes

{{COMPONENTS}}

### Vendors

{{VENDORS}}

---

## Corporate Data, Privacy, and Tech Ethics

1. Have you registered your application in the appropriate tool?
   - [ ] Yes, with APM. APM registration ID: **[TO BE CONFIRMED]**
   - [ ] No, explain: **[TO BE CONFIRMED]**

2. Have you completed the IGR Form?
   - [ ] Yes — link: **[TO BE CONFIRMED]**
   - [ ] No, explain: **[TO BE CONFIRMED]**

3. Assessments required:
   - PIMS: **[TO BE CONFIRMED]**
   - GPA: **[TO BE CONFIRMED]**
   - DMG: **[TO BE CONFIRMED]**
   - AIIA: **[TO BE CONFIRMED]**

---

## Considerations for AI Applications

{{AI_SECTION}}

---

## Reliability, Resiliency and Scalability

{{RELIABILITY}}

---

## End to End Testing

**End to End test team focal point:** [TO BE CONFIRMED]

**Links to test cases:** [TO BE CONFIRMED]

**Links to test results:** [TO BE CONFIRMED]

---

## Service Operations

{{SERVICE_OPERATIONS}}

### Dev Operations Use Cases

| # | Use Case description | Testcase and expected results |
|:--|:--------------------|:------------------------------|
| 1 | As DevOps I must be alerted when | application pods are not running |
| 2 | As DevOps I must be alerted when | health endpoint reports degradation |
| 3 | As DevOps I must be alerted when | application is throwing ERRORs |

---

## Communication

{{COMMUNICATION}}

### Components & Teams Impacted

{{TEAMS_IMPACTED}}

---

## Documentation

### Customer Documents

[TO BE CONFIRMED]

### Adopter/Internal Documents

[TO BE CONFIRMED]

### Runbooks

[TO BE CONFIRMED]

---

## Security Impacts

{{SECURITY_IMPACTS}}

---

## Translation

{{TRANSLATION}}

---

## References

[To be added by the service team]
