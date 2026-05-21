# mlowcher.ivanti_itsm

Starter Ansible collection for automating Ivanti Neurons for ITSM / Ivanti Service Manager using the REST/OData Business Object API.

This collection is intentionally REST-first. Ivanti ITSM tenant schemas are often customized, so the modules support both simple common incident parameters and raw `fields` dictionaries.

## Included

- `mlowcher.ivanti_itsm.ivanti_incident`
  - create, get, update, delete, close, resolve incident records
- `mlowcher.ivanti_itsm.ivanti_business_object`
  - generic CRUD for any Ivanti business object such as `incidents`, `changes`, `employees`, or custom objects
- `ivanti_incident` role
  - thin role wrapper around the incident module
- Example playbooks for AAP / Event-Driven Ansible workflows

## Install locally

```bash
ansible-galaxy collection install ./mlowcher-ivanti_itsm-0.1.0.tar.gz
```

Or during development:

```bash
mkdir -p ~/.ansible/collections/ansible_collections/mlowcher
cp -R . ~/.ansible/collections/ansible_collections/mlowcher/ivanti_itsm
```

## Authentication

Supported options:

1. Existing API token/session key:

```yaml
ivanti_token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
```

2. Username/password login:

```yaml
ivanti_username: "{{ lookup('env', 'IVANTI_USERNAME') }}"
ivanti_password: "{{ lookup('env', 'IVANTI_PASSWORD') }}"
ivanti_tenant: "{{ lookup('env', 'IVANTI_TENANT') }}"
```

The module uses `/api/rest/authentication/login` for username/password auth and `/api/odata/businessobject/<object>` for business object operations.

## Create an incident

```yaml
- name: Create Ivanti incident for network drift
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Open incident
      mlowcher.ivanti_itsm.ivanti_incident:
        base_url: "https://your-tenant.example.com"
        token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
        validate_certs: true
        state: present
        subject: "Network drift detected on {{ inventory_hostname | default('router1') }}"
        description: "AAP detected NTP drift. Job ID: {{ tower_job_id | default('manual') }}"
        priority: High
        fields:
          Category: Network
          Source: Ansible Automation Platform
      register: incident_result

    - debug:
        var: incident_result.record
```

## Update an incident

An update is just `state: present` with a `rec_id` — when the RecId is set the
module patches the existing record instead of creating a new one.

```yaml
- name: Update incident status
  mlowcher.ivanti_itsm.ivanti_incident:
    base_url: "https://your-tenant.example.com"
    token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
    state: present
    rec_id: "{{ ivanti_rec_id }}"
    fields:
      Status: Active
      Description: "AAP remediation workflow has started."
```

The `playbooks/update_incident.yml` playbook wraps this for the common
closed-loop case: posting **progress from an Ansible run** back onto the
incident and optionally changing its status. It is survey-friendly — drive it
from an AAP job template with these extra-vars:

```bash
ansible-playbook playbooks/update_incident.yml \
  -e ivanti_rec_id=<RecId> \
  -e ivanti_status=Active \
  -e 'ivanti_progress_output=Remediation play completed: NTP reset on rtr1'
```

- `ivanti_rec_id` — the incident to update (required).
- `ivanti_progress_output` — text/stdout from the prior play, written to the
  tenant's progress field (`ivanti_progress_field`, default `Notes`).
- `ivanti_status` — optional; left unset, the existing status is untouched
  (via `default(omit, true)`).

Provide at least one of `ivanti_progress_output` or `ivanti_status`. Note that
the module **overwrites** the progress field rather than appending; for a
running history, query the current value first or write to a dedicated Journal
business object with `ivanti_business_object`.

## Close an incident using a Quick Action

```yaml
- name: Close incident
  mlowcher.ivanti_itsm.ivanti_incident:
    base_url: "https://your-tenant.example.com"
    token: "{{ lookup('env', 'IVANTI_TOKEN') }}"
    state: closed
    rec_id: "{{ ivanti_rec_id }}"
    quick_action: Close
    fields:
      Resolution: "Resolved by Ansible Automation Platform"
```

## Configure AAP (config as code)

Everything this solution needs in Ansible Automation Platform is declared as code so a new user can stand it up in one command. The layer uses native, certified collections: `ansible.platform` for gateway objects, `ansible.controller` for controller objects, and `ansible.eda` for Event-Driven Ansible.

What it creates: an organization, an execution environment, a localhost inventory, a **custom Ivanti credential type** (injecting `IVANTI_BASE_URL` / `IVANTI_TOKEN`), an Ivanti credential, a project synced from this repo, job templates for create/query/update/close (with the Ivanti credential attached), and a decision environment + EDA project + rulebook activation for the closed-loop drift→incident flow.

1. Edit the single config file `vars/aap_config.yml` (hostnames, image names, org).
2. Export connection settings (no secrets in git):

```bash
export AAP_HOSTNAME="https://aap.example.com"
export AAP_TOKEN="<your-aap-oauth-token>"
export IVANTI_TOKEN="<your-ivanti-api-token>"   # stored only in the AAP credential
```

3. Install dependencies and apply:

```bash
ansible-galaxy collection install -r collections/requirements.yml
ansible-playbook playbooks/configure_aap.yml          # add --check to preview
```

The Ivanti API token is read from `IVANTI_TOKEN` at apply time and lives only inside the AAP custom credential — it is never written to git or a vault file. Job templates reference that credential, so playbooks receive `IVANTI_BASE_URL` / `IVANTI_TOKEN` as environment variables at run time.

### Custom credential type example

This is the credential type the config-as-code layer creates, exactly as declared in `vars/aap_config.yml`. The `inputs` define the credential's fields (the token is `secret: true`, so AAP masks it); the `injectors` expose those fields to playbooks as `IVANTI_*` environment variables at job run time:

```yaml
aap_credential_type:
  name: "Ivanti ITSM"
  inputs:
    fields:
      - id: ivanti_base_url
        type: string
        label: "Ivanti Base URL"
      - id: ivanti_token
        type: string
        label: "Ivanti API Token"
        secret: true
    required:
      - ivanti_base_url
      - ivanti_token
  injectors:
    env:
      # !unsafe is required: this Jinja is rendered by AAP at job run time,
      # not by the playbook that creates the credential type. Without it,
      # configure_aap.yml would resolve these to empty strings.
      IVANTI_BASE_URL: !unsafe "{{ ivanti_base_url }}"
      IVANTI_TOKEN: !unsafe "{{ ivanti_token }}"
```

To add another field (for example a `tenant`), add it under `inputs.fields`, reference it in an injector, and the modules will receive it. The modules already read `IVANTI_BASE_URL` and `IVANTI_TOKEN` from the environment, so no module change is needed for those two.

## Build the execution environment

Job templates run inside an execution environment (EE) — a container image
that bundles this collection and its dependencies. A custom EE definition
lives in `execution-environment/`, built with
[`ansible-builder`](https://ansible.readthedocs.io/projects/builder/) on the
Red Hat certified `ee-supported-rhel9` base.

The definition reuses `collections/requirements.yml` as its single source of
galaxy dependencies, so the image, the AAP project sync, and local installs
all resolve the same collections.

```bash
# The supported base image is pulled from registry.redhat.io.
podman login registry.redhat.io

ansible-builder build \
  --file execution-environment/execution-environment.yml \
  --context execution-environment/context \
  --tag registry.example.com/ivanti-itsm-ee:latest

# Push it to your registry, then point AAP at the tag:
podman push registry.example.com/ivanti-itsm-ee:latest
```

Set `aap_execution_environment.image` in `vars/aap_config.yml` to the pushed
tag, and `configure_aap.yml` will register the EE and attach it to every job
template. Add tenant-specific Python or system packages by editing
`execution-environment/requirements.txt` and `execution-environment/bindep.txt`.

## Notes

Ivanti business object names usually need to be plural, for example `incidents`, `changes`, or `employees`. Custom tenant schemas may require different field names, so use `fields` for site-specific payloads.

## References

- Ivanti API hub: https://www.ivanti.com/support/api
- Ivanti REST API intro: https://help.ivanti.com/ht/help/en_US/ISM/2022/admin/Content/Configure/API/RestAPI-Introduction.htm
- Get business objects: https://help.ivanti.com/ht/help/en_US/ISM/2022/admin/Content/Configure/API/Get-All-Business-Objects.htm
