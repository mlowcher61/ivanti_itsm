#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: ivanti_incident
short_description: Manage Ivanti ITSM incidents
version_added: "0.1.0"
description:
  - Create, query, update, delete, close, or resolve Ivanti Neurons for ITSM / Service Manager incidents.
options:
  base_url:
    required: true
    type: str
    description: Ivanti tenant base URL.
  token:
    type: str
    no_log: true
    description: Existing REST API token, JWT, or session key.
  username:
    type: str
    description: Username for login authentication.
  password:
    type: str
    no_log: true
    description: Password for login authentication.
  tenant:
    type: str
    description: Optional tenant name for login authentication.
  validate_certs:
    type: bool
    default: true
  timeout:
    type: int
    default: 30
  state:
    type: str
    choices: [present, absent, query, closed, resolved]
    default: present
  rec_id:
    type: str
    description: Incident RecId.
  query:
    type: str
    description: Raw OData query string.
  subject:
    type: str
    description: Incident subject.
  description:
    type: str
    description: Incident description.
  priority:
    type: str
    description: Incident priority value matching your tenant schema.
  status:
    type: str
    description: Incident status value matching your tenant schema.
  fields:
    type: dict
    default: {}
    description: Additional or overriding incident fields.
  quick_action:
    type: str
    description: Quick Action name used for closed/resolved states. Defaults to Close or Resolve.
author:
  - Mark Lowcher (@mlowcher61)
'''

EXAMPLES = r'''
- name: Open an Ivanti incident
  mlowcher.ivanti_itsm.ivanti_incident:
    base_url: https://tenant.example.com
    token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
    state: present
    subject: Network drift detected
    description: AAP detected NTP drift on rtr1
    priority: High
    fields:
      Category: Network
      Source: Ansible Automation Platform

- name: Query active incidents
  mlowcher.ivanti_itsm.ivanti_incident:
    base_url: https://tenant.example.com
    token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
    state: query
    query: "$filter=Status eq 'Active'&$top=10"

- name: Close an incident
  mlowcher.ivanti_itsm.ivanti_incident:
    base_url: https://tenant.example.com
    token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
    state: closed
    rec_id: "{{ ivanti_rec_id }}"
    fields:
      Resolution: Resolved by Ansible Automation Platform
'''

RETURN = r'''
record:
  description: Ivanti response payload.
  returned: always
  type: dict
status_code:
  description: HTTP status code returned by Ivanti.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.mlowcher.ivanti_itsm.plugins.module_utils.ivanti_client import IvantiClient, IvantiError


def incident_fields(params):
    fields = {}
    if params.get('subject'):
        fields['Subject'] = params['subject']
    if params.get('description'):
        fields['Description'] = params['description']
    if params.get('priority'):
        fields['Priority'] = params['priority']
    if params.get('status'):
        fields['Status'] = params['status']
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
        state=dict(type='str', choices=['present', 'absent', 'query', 'closed', 'resolved'], default='present'),
        rec_id=dict(type='str'),
        query=dict(type='str'),
        subject=dict(type='str'),
        description=dict(type='str'),
        priority=dict(type='str'),
        status=dict(type='str'),
        fields=dict(type='dict', default={}),
        quick_action=dict(type='str'),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    p = module.params
    client = IvantiClient(module, p['base_url'], token=p['token'], username=p['username'],
                          password=p['password'], tenant=p['tenant'],
                          validate_certs=p['validate_certs'], timeout=p['timeout'])
    try:
        state = p['state']
        rec_id = p['rec_id']
        fields = incident_fields(p)
        object_name = 'incidents'

        if state == 'query':
            status, data = client.get_object(object_name, rec_id=rec_id, query=p['query'])
            if status != 200:
                module.fail_json(msg='Ivanti incident query failed', status_code=status, response=data)
            module.exit_json(changed=False, status_code=status, record=data)

        if state == 'present':
            if not fields:
                module.fail_json(msg='At least one of subject, description, priority, status, or fields is required')
            if module.check_mode:
                module.exit_json(changed=True, status_code=0, record={'planned_fields': fields})
            if rec_id:
                status, data = client.update_object(object_name, rec_id, fields)
                expected = [200, 204]
            else:
                status, data = client.create_object(object_name, fields)
                expected = [200, 201]
            if status not in expected:
                module.fail_json(msg='Ivanti incident write failed', status_code=status, response=data)
            module.exit_json(changed=True, status_code=status, record=data)

        if state == 'absent':
            if not rec_id:
                module.fail_json(msg='rec_id is required when state=absent')
            if module.check_mode:
                module.exit_json(changed=True, status_code=0, record={'planned_delete': rec_id})
            status, data = client.delete_object(object_name, rec_id)
            if status not in [200, 202, 204, 404]:
                module.fail_json(msg='Ivanti incident delete failed', status_code=status, response=data)
            module.exit_json(changed=(status != 404), status_code=status, record=data)

        if state in ['closed', 'resolved']:
            if not rec_id:
                module.fail_json(msg='rec_id is required when state=%s' % state)
            action = p['quick_action'] or ('Close' if state == 'closed' else 'Resolve')
            if module.check_mode:
                module.exit_json(changed=True, status_code=0, record={'planned_quick_action': action, 'fields': fields})
            status, data = client.quick_action(object_name, rec_id, action, fields=fields)
            if status not in [200, 201, 202, 204]:
                module.fail_json(msg='Ivanti incident quick action failed', status_code=status, response=data)
            module.exit_json(changed=True, status_code=status, record=data)

    except IvantiError as exc:
        module.fail_json(msg=str(exc))


def main():
    run_module()


if __name__ == '__main__':
    main()
