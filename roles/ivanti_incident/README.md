# ivanti_incident

Thin wrapper role around the `mlowcher61.ivanti_itsm.ivanti_incident` module for
creating, querying, updating, closing, and resolving incidents in Ivanti Neurons
for ITSM / Ivanti Service Manager. It is driven entirely by `ivanti_*` variables
so it slots cleanly into AAP job templates.

## Requirements

- Ansible Automation Platform / ansible-core >= 2.16
- Network access to your Ivanti tenant REST/OData API
- An Ivanti API token (or username/password) supplied via variables or `IVANTI_*` environment variables

## Role Variables

| Variable | Default | Description |
|---|---|---|
| `ivanti_base_url` | `""` | Ivanti tenant base URL (required). |
| `ivanti_token` | `IVANTI_TOKEN` env | REST API token / session key. |
| `ivanti_username` | `IVANTI_USERNAME` env | Username for login auth (if no token). |
| `ivanti_password` | `IVANTI_PASSWORD` env | Password for login auth. |
| `ivanti_tenant` | `IVANTI_TENANT` env | Optional tenant name for login. |
| `ivanti_validate_certs` | `true` | Validate TLS certificates. |
| `ivanti_incident_state` | `present` | `present`, `absent`, `query`, `closed`, or `resolved`. |
| `ivanti_incident_rec_id` | `""` | Incident RecId (for update/close/resolve/delete). |
| `ivanti_incident_subject` | `""` | Incident subject. |
| `ivanti_incident_description` | `""` | Incident description. |
| `ivanti_incident_priority` | `""` | Priority value matching your tenant schema. |
| `ivanti_incident_status` | `""` | Status value matching your tenant schema. |
| `ivanti_incident_fields` | `{}` | Raw `fields` dict for site-specific payloads. |
| `ivanti_incident_query` | `""` | Raw OData query string (for `query`). |
| `ivanti_incident_quick_action` | `""` | Quick Action name for `closed`/`resolved`. |

Empty variables are omitted from the module call, so they don't send empty parameters.

## Example Playbook

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: mlowcher61.ivanti_itsm.ivanti_incident
      vars:
        ivanti_base_url: "https://tenant.example.com"
        ivanti_incident_subject: "Drift detected on rtr1"
        ivanti_incident_description: "Configuration drift remediated by AAP."
        ivanti_incident_priority: "3"
```

## License

MIT

## Author Information

Mark Lowcher (@mlowcher61)
