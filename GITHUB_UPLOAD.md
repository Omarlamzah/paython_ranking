# Upload this project to GitHub

Follow these steps from your **laptop** (in the project folder).

---

## 1. Create a new repository on GitHub

1. Go to **https://github.com** and sign in.
2. Click the **+** (top right) → **New repository**.
3. **Repository name:** e.g. `GoogleRecaptchaBypass` or `nextpital-search`.
4. Choose **Public**.
5. **Do not** check "Add a README" (you already have files).
6. Click **Create repository**.

You’ll see a page with a URL like:  
`https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git`

---

## 2. Upload the project from your laptop

Open a terminal on your **laptop**, then:

```bash
cd /home/nextpital/Desktop/jball/GoogleRecaptchaBypass-main
git init
git add .
git commit -m "Initial commit: Google search loop, reCAPTCHA solver, VPS setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

**Replace** `YOUR_USERNAME` and `YOUR_REPO_NAME` with your real GitHub username and repo name.

Example if your username is `nextpital` and repo is `GoogleRecaptchaBypass`:

```bash
git remote add origin https://github.com/nextpital/GoogleRecaptchaBypass.git
git push -u origin main
```

When asked for credentials:
- **Username:** your GitHub username
- **Password:** use a **Personal Access Token** (GitHub no longer accepts account password for push). Create one: GitHub → Settings → Developer settings → Personal access tokens → Generate new token (with `repo` scope).

---

## 3. Done

Refresh the repo page on GitHub; all project files should be there.  
`.venv` and `.2captcha_key` are not uploaded (they’re in `.gitignore`).

---

## Later: push changes

After you change code:

```bash
cd /home/nextpital/Desktop/jball/GoogleRecaptchaBypass-main
git add .
git commit -m "Describe your change"
git push
```
