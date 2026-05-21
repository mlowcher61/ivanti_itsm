# AAP / EDA Integration Pattern

## Closed-loop remediation flow

1. Monitoring or drift detection finds an issue.
2. Event-Driven Ansible receives an event through webhook, Kafka, or another event source.
3. AAP workflow launches a remediation playbook.
4. This collection creates an Ivanti incident or change record.
5. Approval can happen in Ivanti or AAP depending on the customer process.
6. AAP remediates the issue.
7. This collection updates or closes the Ivanti record.

## Example EDA rulebook action

```yaml
---
- name: Ivanti drift incident rulebook
  hosts: all
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5000

  rules:
    - name: Open Ivanti incident for drift
      condition: event.payload.drift_detected == true
      action:
        run_job_template:
          name: Create Ivanti Incident
          organization: Default
          job_args:
            extra_vars:
              device_name: "{{ event.payload.device }}"
              drift_resource: "{{ event.payload.resource }}"
```

## AAP credential recommendation

Create a custom credential type for Ivanti:

Inputs:

```yaml
fields:
  - id: ivanti_base_url
    type: string
    label: Ivanti Base URL
  - id: ivanti_token
    type: string
    label: Ivanti API Token
    secret: true
required:
  - ivanti_base_url
  - ivanti_token
```

Injectors:

```yaml
env:
  IVANTI_BASE_URL: "{{ ivanti_base_url }}"
  IVANTI_TOKEN: "{{ ivanti_token }}"
```
