# Security Policy

## About CASCADE Security

CASCADE Enterprise RAM was built with security as a core requirement. The codebase includes:

- **SQL Injection Prevention**: All database operations use parameterized queries
- **Input Validation**: Comprehensive validation with strict limits on all inputs
- **Rate Limiting**: Per-tool and global request limits with sliding window algorithm
- **Error Sanitization**: Sensitive data (paths, credentials, IPs) scrubbed from all error messages
- **Audit Logging**: All operations logged with session and request tracking
- **Dual-Write Integrity**: RAM writes verified against disk truth on every sync cycle

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x.x   | Active support |
| < 2.0   | Not supported |

## Reporting a Vulnerability

If you discover a security vulnerability in CASCADE Enterprise, please report it privately.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### Contact

**Email**: glass@cipscorps.io
**Subject Line**: [SECURITY] CASCADE Enterprise Vulnerability Report

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested fix (if you have one)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Resolution Timeline**: Provided after assessment

### What to Expect

1. We will acknowledge your report within 48 hours
2. We will investigate and assess the severity
3. We will work on a fix and coordinate disclosure timing with you
4. We will credit you in the security advisory (unless you prefer anonymity)

## Responsible Disclosure

We kindly request that you:

- Allow reasonable time for us to fix the issue before public disclosure
- Do not exploit vulnerabilities beyond proof of concept
- Do not access, modify, or delete other users' data
- Act in good faith to avoid privacy violations and service disruption

## Contact

- **Security Issues**: glass@cipscorps.io
- **General**: https://cipscorps.io

---

*CIPS Corp - https://cipscorps.io*
