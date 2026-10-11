#!/usr/bin/env python3
"""
Generate per-page RAW-MARKDOWN "twins" for every blog post.

For a post served at  /<path>/  this writes a twin served at  /<path>.md
whose body is the post's raw markdown: the title as "# Title" followed by
the post body (reused verbatim from _posts/ — never re-translated).

WHY THE .html SOURCE EXTENSION AND THE {% raw %} WRAPPER
--------------------------------------------------------
GitHub Pages runs jekyll-optional-front-matter, which sends every *.md
SOURCE file through the Markdown converter -> HTML. A naive .md file would
therefore be served as HTML, defeating the purpose. So each twin SOURCE
file uses a .html extension with an explicit `permalink: /<path>.md`:

  * .html extension   -> Jekyll does NOT run the Markdown converter, the
                         body passes through untouched.
  * {% raw %} wrapper -> Jekyll does NOT run Liquid on the body either, so
                         any stray {{ }} / {% %} in future post content is
                         emitted literally.
  * permalink /x/y.md -> Jekyll unescapes %20 for the on-disk path, so a
                         category URL like /hukum%20perdata/.../slug.md is
                         written to "hukum perdata/.../slug.md" on disk,
                         exactly where Pages maps the %20 request.

The output is raw markdown (headings as "#", not "<h1>"). Verified in a
local build; see the website-developer MEMORY.md.

These twins are COMMITTED STATIC FILES. Re-run this script whenever posts
are added, removed, renamed, retitled, or their body changes:

    python3 _tools/gen-md-twins.py

Post URLs are read from Jekyll itself (a throwaway manifest page built to a
temp dir) so category URL-encoding is never re-implemented by hand.

Requires the local user-gem jekyll (the one the advokatluthfi-site-verify
skill uses). Override its path with JEKYLL_BIN if it moves.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

SITE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
POSTS = os.path.join(SITE, "_posts")
OUT = os.path.join(SITE, "md")  # twin SOURCE files (no /md/ output; explicit permalinks)
JEKYLL_BIN = os.environ.get("JEKYLL_BIN", os.path.expanduser("~/.gem/ruby/2.6.0/bin/jekyll"))

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def split_front_matter(text):
    m = FM_RE.match(text)
    if not m:
        raise ValueError("no front matter")
    return m.group(1), m.group(2)


def get_title(front_matter):
    # `title:` may be plain or quoted and may contain ':' — take the rest of the line.
    for line in front_matter.splitlines():
        if line.startswith("title:"):
            val = line[len("title:"):].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val
    raise ValueError("no title in front matter")


def build_manifest():
    """Build the site once with a throwaway manifest page; return {source_path: url}."""
    manifest_page = os.path.join(SITE, "twin_manifest.html")
    with open(manifest_page, "w", encoding="utf-8") as f:
        f.write("---\nlayout: null\nsitemap: false\npermalink: /twin-manifest.txt\n---\n"
                "{% for post in site.posts %}{{ post.path }}:::{{ post.url }}\n{% endfor %}")
    tmp = tempfile.mkdtemp(prefix="mdtwin-build-")
    try:
        env = dict(os.environ, LC_ALL="en_US.UTF-8", LANG="en_US.UTF-8",
                   JEKYLL_NO_BUNDLER_REQUIRE="true", JEKYLL_ENV="production")
        subprocess.run([JEKYLL_BIN, "build", "--destination", tmp], cwd=SITE, env=env,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        manifest = {}
        with open(os.path.join(tmp, "twin-manifest.txt"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ":::" in line:
                    path, url = line.split(":::", 1)
                    manifest[path] = url
        return manifest
    finally:
        os.remove(manifest_page)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    manifest = build_manifest()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)  # drop stale twins so deletions/renames propagate
    os.makedirs(OUT)
    count = 0
    for src in sorted(glob.glob(os.path.join(POSTS, "*.md"))):
        base = os.path.basename(src)
        if base == "_defaults.md":
            continue
        rel = "_posts/" + base
        url = manifest.get(rel)
        if not url:
            print("WARN: no URL in manifest for " + rel, file=sys.stderr)
            continue
        with open(src, encoding="utf-8") as f:
            fm, body = split_front_matter(f.read())
        title = get_title(fm)
        permalink = url.rstrip("/") + ".md"
        body = body.lstrip("\n").rstrip() + "\n"
        twin = ("---\n"
                "layout: null\n"
                "sitemap: false\n"
                "permalink: " + permalink + "\n"
                "---\n"
                "{% raw %}# " + title + "\n\n" + body + "{% endraw %}\n")
        with open(os.path.join(OUT, base[:-3] + ".html"), "w", encoding="utf-8") as f:
            f.write(twin)
        count += 1
    print("generated %d markdown twins into %s" % (count, OUT))


if __name__ == "__main__":
    main()
