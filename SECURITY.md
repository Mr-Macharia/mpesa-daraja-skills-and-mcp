# Security policy

This project moves real money when it is configured for production, so security reports are a priority.

## Reporting a vulnerability

**Please don't open a public issue.** Report privately through GitHub instead:
- **Where:** [Security → Report a vulnerability](https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/security/advisories/new) on this repository.
- **What to include:**
  - what an attacker could do (e.g. trigger a payout, read secrets, bypass the production guard);
  - steps to reproduce;
  - affected version or commit.

You'll get an acknowledgement within **3 working days**. Confirmed issues are fixed in a patch release and credited in the advisory, unless you'd rather stay anonymous.

**Never include real credentials in a report.** That covers consumer keys, passkeys, initiator passwords and SecurityCredentials. If you've exposed one, rotate it in the Daraja portal first.

## In scope

- Ways to move money that bypass the server's safeguards:
  - the production guard (`DARAJA_ALLOW_LIVE_MONEY_MOVEMENT`);
  - idempotency (a repeated key paying twice);
  - pre-send validation.
- Secret leakage through tool output, logs, error messages or the state database.
- The built-in callback receiver: token bypass, request forgery that changes recorded payment outcomes, denial of service.
- Unsafe guidance in the skills that would lead an agent to mishandle money or credentials.

## Out of scope

- Vulnerabilities in Safaricom's Daraja platform itself. Report those to Safaricom.
- Issues that require an attacker who already controls the machine or its environment variables.

## Supported versions

Security fixes go to the latest release on PyPI (`mpesa-daraja`) and to `main`.

## Hardening guidance for users

- Keep `DARAJA_ENV=sandbox` until you have tested end to end.
- Leave `DARAJA_ALLOW_LIVE_MONEY_MOVEMENT` unset unless an agent genuinely needs to move live money.
- Give the API initiator only the roles it needs. Store secrets in a secret manager, not in committed config files.
- In production, run the callback receiver behind TLS with a long random `DARAJA_CALLBACK_TOKEN`. Use your own receiver if you need to reject C2B payments.
