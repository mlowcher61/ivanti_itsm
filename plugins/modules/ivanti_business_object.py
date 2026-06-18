#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: ivanti_business_object
short_description: Manage Ivanti ITSM business objects through REST/OData
version_added: "0.1.0"
description:
  - Create, read, update, or delete Ivanti Neurons for ITSM / Service Manager business objects.
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
  object_name:
    description: Plural Ivanti business object name, for example C(incidents), C(changes), or C(employees).
    required: true
    type: str
  state:
    description: Desired state/action.
    type: str
    choices: [present, absent, query]
    default: present
  rec_id:
    description: Ivanti RecId for get, update, or delete operations.
    type: str
  fields:
    description: Business object fields to create or update.
    type: dict
    default: {}
  query:
    description: Raw OData query string, for example C($top=10&$filter=Status eq 'Active').
    type: str
  check_mode:
    description: Supports Ansible check mode for create/update/delete.
    type: bool
    default: false
author:
  - Mark Lowcher (@mlowcher61)
'''

EXAMPLES = r'''
- name: Get open incidents
  mlowcher.ivanti_itsm.ivanti_business_object:
    base_url: https://tenant.example.com
    token: "{{ ivanti_token }}"
    object_name: incidents
    state: query
    query: "$top=10&$filter=Status eq 'Active'"

- name: Create a custom business object record
  mlowcher.ivanti_itsm.ivanti_business_object:
    base_url: https://tenant.example.com
    token: "{{ ivanti_token }}"
    object_name: incidents
    state: present
    fields:
      Subject: Network drift detected
      Description: Created by Ansible Automation Platform
'''

RETURN = r'''
record:
  description: Ivanti response record or response payload.
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
from ansible_collections.mlowcher.ivanti_itsm.plugins.module_utils.ivanti_client import IvantiClient, IvantiError


def run_module():
    argument_spec = dict(
        base_url=dict(type='str', required=True),
        token=dict(type='str', no_log=True),
        username=dict(type='str'),
        password=dict(type='str', no_log=True),
        tenant=dict(type='str'),
        validate_certs=dict(type='bool', default=True),
        timeout=dict(type='int', default=30),
        object_name=dict(type='str', required=True),
        state=dict(type='str', choices=['present', 'absent', 'query'], default='present'),
        rec_id=dict(type='str'),
        fields=dict(type='dict', default={}),
        query=dict(type='str'),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    p = module.params

    client = IvantiClient(module, p['base_url'], token=p['token'], username=p['username'],
                          password=p['password'], tenant=p['tenant'],
                          validate_certs=p['validate_certs'], timeout=p['timeout'])
    try:
        state = p['state']
        rec_id = p['rec_id']
        object_name = p['object_name']
        fields = p['fields'] or {}

        if state == 'query':
            status, data = client.get_object(object_name, rec_id=rec_id, query=p['query'])
            if status not in [200]:
                module.fail_json(msg='Ivanti query failed', status_code=status, response=data)
            module.exit_json(changed=False, status_code=status, record=data)

        if state == 'present':
            if not fields:
                module.fail_json(msg='fields is required when state=present')
            if module.check_mode:
                module.exit_json(changed=True, status_code=0, record={'planned_fields': fields})
            if rec_id:
                status, data = client.update_object(object_name, rec_id, fields)
                expected = [200, 204]
            else:
                status, data = client.create_object(object_name, fields)
                expected = [200, 201]
            if status not in expected:
                module.fail_json(msg='Ivanti write failed', status_code=status, response=data)
            module.exit_json(changed=True, status_code=status, record=data)

        if state == 'absent':
            if not rec_id:
                module.fail_json(msg='rec_id is required when state=absent')
            if module.check_mode:
                module.exit_json(changed=True, status_code=0, record={'planned_delete': rec_id})
            status, data = client.delete_object(object_name, rec_id)
            if status not in [200, 202, 204, 404]:
                module.fail_json(msg='Ivanti delete failed', status_code=status, response=data)
            module.exit_json(changed=(status != 404), status_code=status, record=data)

    except IvantiError as exc:
        module.fail_json(msg=str(exc))


def main():
    run_module()


if __name__ == '__main__':
    main()
