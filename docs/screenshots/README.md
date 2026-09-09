# Dashboard screenshots

These are actual Playwright captures of the running container, not design mockups.

- Source: `fbe92707de72cba0bac504a21daf963e94e1b1ec`
- [Passing native Linux run](https://github.com/ahmed-sami94/LAMP-/actions/runs/34408734668)
- Capture artifact: `verification-arm64`, ID `10126483315`
- Desktop viewport: 1366 x 900; mobile: 390 x 844; tablet: 820 x 1180.
- Full-page PNG captures include synthetic Studio, Journal, WordPress and Joomla
  websites. Credentials are generated privately and are not visible.
- Pages: Websites, Services, Backups, Activity, WordPress setup and owner sign-in.
- Dashboard captures include Ahmed Sami's copyright, email and website attribution.

The Activity page includes intentionally rejected operations from security tests,
such as invalid hostnames and unconfirmed restores. These demonstrate validation;
the associated acceptance checks passed.

Service and filesystem measurements are from the disposable CI container and
its website-volume filesystem. They are not minimum hardware requirements or
measurements of a user's workstation. Values vary between runs.
