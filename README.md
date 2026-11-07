# The Encyclopedia

A small static website that lists my self-contained HTML learning pages ("capsules") and lets me search them. No server, no build step, no dependencies.

**How it's organised:** the home page shows one **collection** per `topic` in `capsules.json` (e.g. "Money & Banking"). To start a new collection, give a capsule a new topic name. Spelling and capitals must match exactly to land in the same collection. Clicking a capsule opens it inside the site, with a bar on top to go back to the home page or the collection.

## What's in this folder

| File | What it is |
|---|---|
| `capsules/` | The capsule pages. Finished work, never edited by the scripts. |
| `capsules.json` | The list of capsules (title, topic, tags, dates, status). **This is the file you edit.** |
| `update.py` | Syncs `capsules.json` with the `capsules/` folder and checks the pages. |
| `capsules-data.js` | Made by `update.py`. Don't edit it by hand. |
| `index.html` | The library page. |

## Add a capsule

1. Copy the `.html` file into `capsules/`. Use a simple file name, e.g. `bond-duration.html`.
2. Run `update.py` (see below). It adds a new entry to `capsules.json` with `status: "draft"`. It fills in the title and summary from the page's `<title>` and `<meta name="description">` when they exist. Everything else says `"TODO"`.
3. Open `capsules.json` and replace each `"TODO"`:
   - `topic`: e.g. `"Fixed Income"`
   - `tags`: a list, e.g. `["bonds", "duration", "interest rates"]`
   - `summary`: one line
   - `date_built` and `facts_verified_as_of`: dates written as `YYYY-MM-DD`, e.g. `"2026-11-07"`
   - `status`: change `"draft"` to `"done"` when it's ready to show
4. Run `update.py` again.

Your edits in `capsules.json` are never overwritten. If you delete a capsule file, `update.py` flags its entry so you can remove the entry yourself.

## Run update.py

Open Terminal in this folder and run:

```bash
python3 update.py
```

It prints what it added, which entries point to missing files, and warnings. Warnings cover: unfinished `TODO` fields, a missing `<title>`, a missing viewport tag (needed for phones), and anything a page loads from the internet (scripts, stylesheets, fonts, images). Ordinary links in the text are fine. It never changes your capsule files.

## Test locally

Double-click `index.html`. It opens in your browser and works without a server.

Things to check: search, the topic filter, "Show drafts", the theme button, and that each card opens its capsule. Capsules whose "facts verified" date is more than 6 months old show **Re-check facts**.

## Publish

After any change, run `update.py`, then:

```bash
git add -A
git commit -m "Add capsule: bond duration"
git push
```

GitHub Pages updates the site a minute or two later.

**Everything in this repository is public if the repository is public.** Put only capsules and site files here: no PDFs, notes or personal documents. The `.gitignore` blocks common document types as a safety net.
