# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json
from ansible.module_utils.urls import fetch_url


class IvantiError(Exception):
    pass


class IvantiClient(object):
    def __init__(self, module, base_url, token=None, username=None, password=None, tenant=None,
                 validate_certs=True, timeout=30):
        self.module = module
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.username = username
        self.password = password
        self.tenant = tenant
        self.validate_certs = validate_certs
        self.timeout = timeout

    def authenticate(self):
        if self.token:
            return self.token
        if not self.username or not self.password:
            raise IvantiError('Provide token or username/password authentication.')

        body = {
            'UserName': self.username,
            'Password': self.password,
        }
        if self.tenant:
            body['tenant'] = self.tenant

        status, data = self.request('POST', '/api/rest/authentication/login', body=body, auth_required=False)
        if status not in [200, 201]:
            raise IvantiError('Authentication failed with HTTP status %s: %s' % (status, data))

        if isinstance(data, dict):
            for key in ['token', 'Token', 'sessionKey', 'SessionKey', 'session_key', 'access_token']:
                if data.get(key):
                    self.token = data[key]
                    return self.token
            if data.get('value'):
                self.token = data['value']
                return self.token
        if isinstance(data, str) and data:
            self.token = data.strip('"')
            return self.token

        raise IvantiError('Authentication response did not include a recognizable token/session key.')

    def headers(self, extra_headers=None, auth_required=True):
        h = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if auth_required:
            token = self.token or self.authenticate()
            h['Authorization'] = 'Bearer %s' % token
        if extra_headers:
            h.update(extra_headers)
        return h

    def request(self, method, path, body=None, query=None, extra_headers=None, auth_required=True):
        url = self.base_url + path
        if query:
            url = url + '?' + query.lstrip('?')

        data = None
        if body is not None:
            data = json.dumps(body)

        response, info = fetch_url(
            self.module,
            url,
            data=data,
            method=method,
            headers=self.headers(extra_headers, auth_required=auth_required),
            timeout=self.timeout,
        )

        status = info.get('status', 0)
        raw = None
        if response:
            raw = response.read()
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')

        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
        elif info.get('body'):
            parsed = info.get('body')
        else:
            parsed = {}

        return status, parsed

    def business_path(self, object_name, rec_id=None):
        object_name = object_name.strip('/')
        path = '/api/odata/businessobject/%s' % object_name
        if rec_id:
            path += "('%s')" % rec_id
        return path

    def get_object(self, object_name, rec_id=None, query=None):
        path = self.business_path(object_name, rec_id=rec_id)
        return self.request('GET', path, query=query)

    def create_object(self, object_name, fields):
        return self.request('POST', self.business_path(object_name), body=fields)

    def update_object(self, object_name, rec_id, fields):
        return self.request('PATCH', self.business_path(object_name, rec_id=rec_id), body=fields)

    def delete_object(self, object_name, rec_id):
        return self.request('DELETE', self.business_path(object_name, rec_id=rec_id))

    def add_related(self, object_name, rec_id, relationship_name, fields):
        # Create a child business object and link it to a parent through a relationship
        # navigation property, e.g. POST /businessobject/incidents('RecId')/IncidentContainsJournal.
        # Used for journal notes and any other related-object creation. Relationship names vary
        # by tenant schema; callers pass the exact name (IncidentContainsJournal, ChangeContainsJournal, ...).
        path = self.business_path(object_name, rec_id=rec_id) + '/' + relationship_name.strip('/')
        return self.request('POST', path, body=fields)

    def quick_action(self, object_name, rec_id, action_name, fields=None):
        # Ivanti Quick Action endpoints vary by version/tenant. This default works for many Neurons for ITSM tenants,
        # but override with raw business_object usage if your tenant requires a custom action URL.
        path = '/api/odata/businessobject/%s(\'%s\')/QuickAction.%s' % (object_name, rec_id, action_name)
        return self.request('POST', path, body=(fields or {}))
