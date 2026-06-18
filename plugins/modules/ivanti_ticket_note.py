#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: ivanti_ticket_note
short_description: Add a journal note to an Ivanti ITSM ticket
version_added: "0.2.0"
description:
  - Add a journal note to any Ivanti Neurons for ITSM / Service Manager ticket (incident, change,
    or custom business object).
  - A note is created as a Journal business object linked to the parent ticket through a relationship
    navigation property, for example C(IncidentContainsJournal) or C(ChangeContainsJournal).
  - Typically used as the closing step of closed-loop remediation to record what Ansible did on a ticket.
options:
  base_url:
    description: Ivanti tenant base URL, for example C(https://tenant.example.com).
    required: true
    type: str
  token:
    description: Existing REST API token, JWT, or session key.
    type: str
    no_log: true
  username:
    description: Username for login authentication.
    type: str
  password:
    description: Password for login authentication.
    type: str
    no_log: true
  tenant:
    description: Optional tenant name for login authentication.
    type: str
  validate_certs:
    description: Validate TLS certificates.
    type: bool
    default: true
  timeout:
    description: Request timeout in seconds.
    type: int
    default: 30
  ticket_object:
    description: Plural Ivanti business object name of the parent ticket, for example C(incidents) or C(changes).
    type: str
    default: incidents
  ticket_rec_id:
    description: RecId of the parent ticket the note is attached to.
    required: true
    type: str
  relationship_name:
    description:
      - Relationship navigation property that links the journal note to the parent ticket.
      - Defaults to C(IncidentContainsJournal); use C(ChangeContainsJournal) for changes and the
        matching relationship name for other ticket types.
    type: str
    default: IncidentContainsJournal
  note:
    description: The note text to record on the ticket.
    required: true
    type: str
  note_field:
    description: Ivanti Journal field that the I(note) text is written to.
    type: str
    default: Body
  subject:
    description: Optional note subject, mapped to the Journal C(Subject) field.
    type: str
  category:
    description: Optional journal category, mapped to the Journal C(Category) field. Omitted when unset so tenant defaults apply.
    type: str
  fields:
    description: Additional or overriding Journal fields. Merged last, so values here win over the friendly params.
    type: dict
    default: {}
author:
  - Mark Lowcher (@mlowcher61)
'''

EXAMPLES = r'''
- name: Add an automation result note to an incident
  mlowcher61.ivanti_itsm.ivanti_ticket_note:
    base_url: https://ivanti.example.com
    token: "{{ ivanti_token }}"
    ticket_object: incidents
    ticket_rec_id: "4A2D7B5D6E3C4F12AABBCCDD"
    relationship_name: IncidentContainsJournal
    note: |
      Ansible remediation completed successfully.

      Host: rtr1
      Action: Interface remediation
      Result: Success

- name: Add a note after an AAP workflow approval
  mlowcher61.ivanti_itsm.ivanti_ticket_note:
    base_url: "{{ ivanti_base_url }}"
    token: "{{ ivanti_token }}"
    ticket_object: incidents
    ticket_rec_id: "{{ incident_rec_id }}"
    subject: "AAP Approval Completed"
    note: |
      Workflow approval completed.

      Approved by: {{ approver_name }}
      Job ID: {{ tower_job_id }}
      Status: Approved

- name: Add a change implementation note
  mlowcher61.ivanti_itsm.ivanti_ticket_note:
    base_url: "{{ ivanti_base_url }}"
    token: "{{ ivanti_token }}"
    ticket_object: changes
    ticket_rec_id: "{{ change_rec_id }}"
    relationship_name: ChangeContainsJournal
    subject: "Change Implemented"
    note: |
      Change implementation completed.

      Change Number: {{ change_number }}
      Device Count: {{ device_count }}
      Result: Successful

- name: Add a note using username/password authentication
  mlowcher61.ivanti_itsm.ivanti_ticket_note:
    base_url: https://ivanti.example.com
    username: api_user
    password: "{{ ivanti_password }}"
    tenant: Production
    ticket_object: incidents
    ticket_rec_id: "{{ incident_rec_id }}"
    note: |
      Incident updated by Ansible.
'''

RETURN = r'''
record:
  description: Ivanti response payload for the created journal note.
  returned: always
  type: dict
status_code:
  description: HTTP status code returned by Ivanti.
  returned: always
  type: int
changed:
  description: Whether the module changed Ivanti.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.mlowcher61.ivanti_itsm.plugins.module_utils.ivanti_client import IvantiClient, IvantiError


def note_fields(params):
    fields = {params['note_field']: params['note']}
    if params.get('subject'):
        fields['Subject'] = params['subject']
    if params.get('category'):
        fields['Category'] = params['category']
    fields.update(params.get('fields') or {})
    return fields


def run_module():
    argument_spec = dict(
        base_url=dict(type='str', required=True),
        token=dict(type='str', no_log=True),
        username=dict(type='str'),
        password=dict(type='str', no_log=True),
        tenant=dict(type='str'),
        validate_certs=dict(type='bool', default=True),
        timeout=dict(type='int', default=30),
        ticket_object=dict(type='str', default='incidents'),
        ticket_rec_id=dict(type='str', required=True),
        relationship_name=dict(type='str', default='IncidentContainsJournal'),
        note=dict(type='str', required=True),
        note_field=dict(type='str', default='Body'),
        subject=dict(type='str'),
        category=dict(type='str'),
        fields=dict(type='dict', default={}),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    p = module.params

    client = IvantiClient(module, p['base_url'], token=p['token'], username=p['username'],
                          password=p['password'], tenant=p['tenant'],
                          validate_certs=p['validate_certs'], timeout=p['timeout'])
    try:
        fields = note_fields(p)

        if module.check_mode:
            module.exit_json(changed=True, status_code=0, record={'planned_note': fields})

        status, data = client.add_related(p['ticket_object'], p['ticket_rec_id'],
                                          p['relationship_name'], fields)
        if status not in [200, 201, 204]:
            module.fail_json(msg='Ivanti ticket note creation failed', status_code=status, response=data)
        module.exit_json(changed=True, status_code=status, record=data)

    except IvantiError as exc:
        module.fail_json(msg=str(exc))


def main():
    run_module()


if __name__ == '__main__':
    main()
