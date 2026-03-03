# 11 — SMTP Email Setup (Invite Sending)

This guide explains how to configure ProjectDashboard so admin-generated invites can be sent by email.

## Feature summary

When creating an invite in Admin > Users & Invites:

- admin can enter recipient email
- admin can enable **Send by email**
- admin can edit the message body
- placeholders are supported in message text:
  - `{invite_link}`
  - `{expires_at}`

If SMTP is not configured, email sending will fail with a clear error.

---

## Required environment variables

ProjectDashboard reads SMTP config from environment variables:

- `PDASH_SMTP_HOST` (required)
- `PDASH_SMTP_PORT` (optional, default: `587`)
- `PDASH_SMTP_USER` (optional if server allows anonymous send)
- `PDASH_SMTP_PASS` (required when `PDASH_SMTP_USER` is used)
- `PDASH_SMTP_FROM` (required sender address, e.g. `noreply@yourdomain.com`)
- `PDASH_SMTP_TLS` (optional: `true`/`false`, default: `true`)

---

## Recommended production setup

Edit `/etc/projectdashboard.env`:

```bash
sudo nano /etc/projectdashboard.env
```

Add or update:

```bash
PDASH_SMTP_HOST=smtp.yourprovider.com
PDASH_SMTP_PORT=587
PDASH_SMTP_USER=noreply@yourdomain.com
PDASH_SMTP_PASS=YOUR_APP_PASSWORD_OR_SMTP_PASSWORD
PDASH_SMTP_FROM=noreply@yourdomain.com
PDASH_SMTP_TLS=true
```

Then restart service:

```bash
sudo systemctl restart projectdashboard
sudo systemctl status projectdashboard --no-pager
```

---

## Provider examples

### Gmail (Workspace or personal)

```bash
PDASH_SMTP_HOST=smtp.gmail.com
PDASH_SMTP_PORT=587
PDASH_SMTP_USER=youraccount@gmail.com
PDASH_SMTP_PASS=YOUR_16_CHAR_APP_PASSWORD
PDASH_SMTP_FROM=youraccount@gmail.com
PDASH_SMTP_TLS=true
```

> Use App Passwords (2FA-enabled account). Do not use your normal account password.

### Outlook / Microsoft 365

```bash
PDASH_SMTP_HOST=smtp.office365.com
PDASH_SMTP_PORT=587
PDASH_SMTP_USER=youraccount@yourdomain.com
PDASH_SMTP_PASS=YOUR_PASSWORD_OR_APP_PASSWORD
PDASH_SMTP_FROM=youraccount@yourdomain.com
PDASH_SMTP_TLS=true
```

### Mailgun (SMTP relay)

```bash
PDASH_SMTP_HOST=smtp.mailgun.org
PDASH_SMTP_PORT=587
PDASH_SMTP_USER=postmaster@mg.yourdomain.com
PDASH_SMTP_PASS=YOUR_MAILGUN_SMTP_PASSWORD
PDASH_SMTP_FROM=noreply@yourdomain.com
PDASH_SMTP_TLS=true
```

---

## Security recommendations

- Keep `/etc/projectdashboard.env` readable only by root/service group.
- Use app-specific SMTP credentials (not personal mailbox password).
- Rotate SMTP credentials periodically.
- Use a dedicated sender mailbox (`noreply@...`).
- Configure SPF, DKIM, and DMARC on your domain for better deliverability.

---

## Quick validation steps

1. Configure vars in `/etc/projectdashboard.env`
2. Restart ProjectDashboard service
3. Open Admin > Users & Invites
4. Fill recipient email, enable **Send by email**, generate invite
5. Confirm mail delivery in recipient inbox (and spam folder)

---

## Troubleshooting

### `SMTP not configured (define PDASH_SMTP_HOST and PDASH_SMTP_FROM)`
Set required variables and restart service.

### Authentication errors
Verify `PDASH_SMTP_USER` / `PDASH_SMTP_PASS`; use app passwords where required.

### TLS / certificate issues
Check firewall/proxy restrictions and ensure outbound access to SMTP host/port.

### Email not received
Check spam folder, sender reputation, and DNS records (SPF/DKIM/DMARC).
