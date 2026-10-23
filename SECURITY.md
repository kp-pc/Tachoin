# Tachoin-Coin Security Report

## Responsible Vulnerability Reporting

**Security Contact:** security@tachoin.io

We follow responsible disclosure practices and provide a clear process for security researchers to report vulnerabilities in Tachoin-Coin.

## Vulnerability Types Covered

- **Critical**: Protocol-breaking vulnerabilities, state corruption, consensus failures
- **High**: Security protocol bypass, fund loss vectors, private key extraction
- **Medium**: Non-standard interactions, DoS possibilities, privacy concerns
- **Low**: Configuration issues, user experience problems

## Reporting Process

### 1. Initial Contact
- Email: security@tachoin.io
- Include: description of vulnerability, proof of concept, impact assessment
- Response time: 48-72 hours for initial acknowledgment

### 2. Coordination and Remediation
- We will coordinate patch release schedule to align with researcher preferences
- Provide clear timeline for fix development and testing
- Offer recognition in security advisories

### 3. Public Disclosure
- Vulnerabilities will be disclosed according to our responsible disclosure policy
- Release security advisory with CVE identifiers when applicable
- Coordinate disclosure dates with reporter

## Severity Assessment Matrix

| Severity | Description | Example Impact |
|----------|-------------|----------------|
| CRITICAL | Breaks protocol or causes state corruption | Fund loss, chain split, validator compromise |
| HIGH | Security bypass, fund loss possible | Transaction replay, nonce confusion, double-spend |
| MEDIUM | Edge case exploitation, partial security impact | Nonce reuse, fee evasion, replay attacks |
| LOW | Configuration or user experience issues | Misconfiguration, UI confusion, minor DoS |

## Bug Bounty

We offer rewards for responsibly disclosed critical and high-severity vulnerabilities:

- **Critical**: $10,000 - $50,000
- **High**: $2,500 - $10,000
- **Medium**: $500 - $2,500
- **Low**: Up to $500 for useful, well-documented findings

## What We Don't Bounty

- Denial of service research (unless providing working mitigations)
- Privacy research without concrete security impact
- Social engineering or phishing attempts
- Attacks against third-party services
- Theoretical vulnerabilities without working exploits

## Security Research Guidelines

### What We Encourage

- Protocol and implementation security analysis
- Cryptographic strength assessment
- Consensus security reviews
- Fuzzing and automated testing
- Static analysis and code review

### What We Discourage

- Attacks against production nodes or user funds
- Social engineering or user deception
- Network-level DoS attacks
- Commercial product circumvention

## Incident Response

We maintain a 24/7 security operations team for:

- Critical vulnerability response
- Zero-day incident handling
- Emergency patch deployment
- Security advisory coordination

## Coordinated Disclosure Policy

1. **Private Reporting**: All vulnerabilities reported through official channels
2. **Timely Response**: Acknowledge receipt within 48 hours
3. **Repair Coordination**: Work with researchers on fix timeline
4. **Disclosure Planning**: Plan disclosure dates that protect users
5. **Public Communication**: Release clear, accurate security advisories

## References

- [Common Vulnerability Reporting Guide](https://www.first.org/cvrg/)
- [OWASP Vulnerability Disclosure](https://owasp.org/www-project-vulnerability-disclosure/)
- [CISA Vulnerability Management Framework](https://www.cisa.gov/vulnerability-management)