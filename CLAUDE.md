# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`mlowcher.ivanti_itsm` — an Ansible **collection** that automates Ivanti Neurons for ITSM / Ivanti Service Manager through its REST/OData Business Object API. It is built for Ansible Automation Platform (AAP) and Event-Driven Ansible (EDA), with closed-loop remediation (detect → open incident → remediate → close) as the primary use case.

The collection is intentionally REST-first because Ivanti tenant schemas are heavily customized. Every module accepts a raw `fields` dict so site-specific payloads work without code changes.

## Architecture

All HTTP traffic flows through a single shared client; modules are thin argument-spec wrappers around it.

- **`plugins/module_utils/ivanti_client.py`** — `IvantiClient`, the only place that touches the network (`fetch_url`). Owns authentication, header construction, OData path building (`business_path`), CRUD helpers (`get/create/update/delete_object`), and `quick_action`. Raises `IvantiError` on auth problems. **Put new API behavior here, not in modules.**
- **`plugins/modules/ivanti_business_object.py`** — generic CRUD (`present`/`absent`/`query`) for *any* plural business object (`incidents`, `changes`, `employees`, custom objects). The lowest-level escape hatch.
- **`plugins/modules/ivanti_incident.py`** — opinionated incident module. Adds `closed`/`resolved` states (which call Quick Actions) and `incident_fields()`, which maps friendly params (`subject`, `description`, `priority`, `status`) to Ivanti's PascalCase field names (`Subject`, `Description`, …). Hard-codes `object_name = 'incidents'`.
- **`roles/ivanti_incident/`** — thin role wrapper over the incident module, driven entirely by `defaults/main.yml` vars (`ivanti_*`). Uses `default(omit, true)` so empty vars don't send empty params.
- **`playbooks/`** — `create_incident.yml`, `query_incidents.yml`, `close_incident.yml`. Localhost playbooks demonstrating AAP job-template patterns; they read `IVANTI_*` env vars. Also `configure_aap.yml`, the config-as-code entrypoint.
- **Config-as-code layer** — `playbooks/configure_aap.yml` + `vars/aap_config.yml` + `collections/requirements.yml`. Declaratively builds the AAP objects this solution needs (org, EE, inventory, Ivanti credential type + credential, project, job templates, and EDA decision environment + project + rulebook activation). Uses native certified collections: `ansible.platform` (gateway), `ansible.controller` (controller), `ansible.eda` (EDA). `vars/aap_config.yml` is the single file users edit.
- **`extensions/eda/rulebooks/ivanti_drift.yml`** — the closed-loop rulebook the EDA activation runs (drift webhook → launches the create-incident job template). Lives at the collection-standard `extensions/eda/rulebooks/` path so the EDA project discovers it by filename.

### Key conventions to preserve

- **Modules import the client via the fully-qualified path** `ansible_collections.mlowcher.ivanti_itsm.plugins.module_utils.ivanti_client`. This means modules only resolve when the collection is installed into a collections path (see below) — you cannot run a module file directly from the repo.
- **Business object names are plural** (`incidents`, not `incident`) and OData record access uses `(...)` syntax: `/api/odata/businessobject/incidents('RecId')`.
- **Auth is token-or-login.** If `token` is set it's used as a Bearer token. Otherwise `authenticate()` POSTs to `/api/rest/authentication/login` and probes many possible response keys (`token`, `SessionKey`, `access_token`, `value`, raw string) because the key varies by tenant/version. When adding auth handling, extend that probe list rather than assuming one shape.
- **Quick Action URLs vary by tenant.** `quick_action()` uses a common default (`.../QuickAction.<name>`); customers with custom action URLs are expected to fall back to `ivanti_business_object`.
- **Secrets use `no_log=True`** on `token`/`password` in every argument spec — keep this on any new credential field.
- **Status-code tolerance is explicit.** Each state checks an allowed list (e.g. delete tolerates `404`, writes accept `200/201/204`). Match this style for new operations.
- Per the maintainer's standards: prefer AAP **custom credentials** (see `docs/AAP_EDA_INTEGRATION.md` for the recommended Ivanti credential type → `IVANTI_BASE_URL`/`IVANTI_TOKEN` injectors) over vaulted files.

### Config-as-code conventions (when editing `configure_aap.yml` / `aap_config.yml`)

- **No secrets in git.** AAP auth comes from `AAP_HOSTNAME` + `AAP_TOKEN` (or `AAP_USERNAME`/`AAP_PASSWORD`) env vars; the Ivanti token is read from `IVANTI_TOKEN` via `lookup('env', ...)` at apply time and stored only inside the AAP credential.
- **Connection params are set once via `module_defaults` action groups**, not per task: `group/ansible.platform.gateway`, `group/ansible.controller.controller`, `group/ansible.eda.eda`. AAP 2.5+ uses the unified `aap_*` param / `AAP_*` env convention (platform + eda); the controller group still uses `controller_host`/`controller_oauthtoken`.
- **Credential-type `injectors` must be `!unsafe`.** Their Jinja (`{{ ivanti_base_url }}`, `{{ ivanti_token }}`) is rendered by AAP at job runtime — without `!unsafe` the configuring playbook would resolve and blank them.
- Object split follows the "ansible.platform when possible" rule: organizations are gateway objects (`ansible.platform`); projects/credentials/credential types/inventories/EEs/job templates are controller objects (`ansible.controller`); decision environments/EDA projects/rulebook activations are `ansible.eda`.
- The EDA rulebook's `run_job_template.organization` is a **literal** string and must match `aap_organization` in `vars/aap_config.yml` (default `"Default"`).

## Build, install, run

There is no test suite, lint config, CI, or `git` repo in this directory yet.

Build the collection artifact:

```bash
ansible-galaxy collection build
```

Install it (required before modules/playbooks will resolve, because of the fully-qualified import path):

```bash
ansible-galaxy collection install ./mlowcher-ivanti_itsm-0.1.0.tar.gz --force
```

For iterative development, symlink/copy the repo into a collections path instead of rebuilding each time:

```bash
mkdir -p ~/.ansible/collections/ansible_collections/mlowcher
ln -s "$PWD" ~/.ansible/collections/ansible_collections/mlowcher/ivanti_itsm
```

Run a playbook (expects `IVANTI_BASE_URL` and `IVANTI_TOKEN` in the environment):

```bash
ansible-playbook playbooks/create_incident.yml -e device_name=rtr1
ansible-playbook playbooks/query_incidents.yml
ansible-playbook playbooks/close_incident.yml -e ivanti_rec_id=<RecId>
```

All modules support check mode (`--check`); in check mode they return a `planned_*` record instead of calling Ivanti.

Apply the config-as-code layer to an AAP instance (requires `AAP_HOSTNAME`, `AAP_TOKEN`, `IVANTI_TOKEN` in the environment):

```bash
ansible-galaxy collection install -r collections/requirements.yml
ansible-playbook playbooks/configure_aap.yml          # --check previews changes
```

Recommended linting (not yet wired in):

```bash
ansible-lint
ansible-test sanity --docker   # run from inside the installed collection path
```

## Versioning

Bump `version` in `galaxy.yml` and `version_added` in module DOCUMENTATION when adding modules/features.
