# Session / secret hygiene

Do **not** upload these to Google Drive (or any cloud sync):

- `.profiles/` — Playwright browser sessions (Reddit / X logins)
- `db/*.db` / `*.db` — local generation history
- `.env` — any API keys

They are already listed in `.gitignore`. Keep sessions only on the machine that posts.

## Clean up existing Drive copies

Trash these folders/files in Drive yourself (the connector cannot trash nested session folders):

- [newest `.profiles`](https://drive.google.com/drive/folders/1dcbkFiSmnIu913mIu0kvWSSwc8YDhKEk)
- [Aug 20 `.profiles`](https://drive.google.com/drive/folders/1vhW-whLHqTWcYgiXEdOlz193L3cebrBl)
- [June `.profiles`](https://drive.google.com/drive/folders/1BMiajRV97b08gFGpSfYYxYon3INSY4Qu)
- [poster.db (copy A)](https://drive.google.com/file/d/1hwt7ozSQnsSZUa3bqLPjfo3T3w1Sgvgk/view)
- [poster.db (copy B)](https://drive.google.com/file/d/1d-YQIIZfDEJgwt5JGCnWOsC1ix4uZgn6/view)

After trashing, change Reddit/X passwords if those profiles might have been exposed.
