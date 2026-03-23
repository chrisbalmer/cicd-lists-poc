# cicd-lists-poc

CI/CD pipeline for managing XSOAR/XSIAM lists via Git.

## Project Structure

```
Packs/
  <PackName>/
    Lists/
      <ListName>/
        <ListName>.json         # demisto-sdk metadata (XSOAR/XSIAM format)
        <ListName>_data.<ext>   # Raw list data file
        metadata.yaml           # CI/CD validation config (optional)
scripts/
  validate.py                   # Main validation script
  upload.py                     # Deploy script using demisto-sdk
  custom_validators/            # Custom validation scripts
    default.py                  # Default custom validator
.github/workflows/
  validate-pr.yml               # Validate, deploy, and auto-merge
```

## metadata.yaml

Each list directory can optionally contain a `metadata.yaml` to configure CI/CD
validation. If omitted, the validator falls back to the `name` and `type` from
`<ListName>.json`.

| Field       | Required | Description |
|-------------|----------|-------------|
| `name`      | No       | Display name for validation output (falls back to `.json` name) |
| `type`      | No       | Validation type: `json`, `csv`, or `plain_text` (falls back to `.json` type) |
| `validator` | No       | Name of a custom validator in `scripts/custom_validators/` |

When `validator` is set, it overrides the type-based validation. This is useful
when the data format needs specific handling (e.g., pipe-delimited CSV).

```yaml
# Standard CSV validation
name: Blocked IPs
type: csv

# CSV with a custom pipe-delimiter validator
name: Firewall Rules
type: csv
validator: pipe_delimited
```

## Adding a New List

1. Download the list from XSOAR/XSIAM with `demisto-sdk download -o Packs/ListManagement -i "<ListName>"`
2. Optionally add `metadata.yaml` to override validation type or use a custom validator
3. Open a PR to `main`

## Custom Validators

Custom validators live in `scripts/custom_validators/` and are referenced by
name in `metadata.yaml` via the `validator` field.

Each validator receives the data file path as the first argument and must exit
with code 0 on success or non-zero on failure.

## CI/CD Workflow

A single workflow (`validate-pr.yml`) handles the full lifecycle:

1. **Validate** — detects which lists changed in the PR and runs validation
2. **Deploy** — uploads changed lists to XSIAM via `demisto-sdk`
3. **Auto-merge** — squash-merges the PR after successful deploy

Deploy runs before merge so that `main` always reflects what is deployed to the
tenant. If the upload fails, the PR stays open and no config drift occurs.

### Required Secrets

| Secret | Purpose |
|---|---|
| `DEMISTO_BASE_URL` | XSOAR/XSIAM server URL |
| `DEMISTO_API_KEY` | API key for authentication |
| `XSIAM_AUTH_ID` | Auth ID for XSIAM |

## Local Validation

```bash
pip install -r requirements.txt
python scripts/validate.py                                                        # Validate all lists
python scripts/validate.py Packs/ListManagement/Lists/ExamplePipeDelimeted        # Validate specific list
```
