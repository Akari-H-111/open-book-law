"""The website in site/: same navigation everywhere, working links, nothing loaded from other sites."""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
PAGES = sorted(SITE.glob("*.html"))
GITHUB = "https://github.com/Akari-H-111/open-book-law"
BOUND = re.compile(
    r"tests\.(count|supported|notsupported)|H(\d+)[ab]?\.(diff|abs|round|low|high|n|verdict|need)"
    r"|H9\.(share|lowshare|highshare)|gl\.[a-z-]+\.(current|old)|gl\.(tested|written|leftout|sample)"
    r"|h9\.(count|n)|date\.both|err\.(count|byGold|byClosed)|mbe\.(all|tests|validation)"
)


def read(path):
    return path.read_text(encoding="utf-8")


def luminance(colour):
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_every_page_has_the_same_navigation_and_the_basic_landmarks():
    assert len(PAGES) >= 10
    navs = set()
    for page in PAGES:
        text = read(page)
        nav = re.search(r'<nav aria-label="Main">.*?</nav>', text, re.S).group(0)
        assert nav.count('aria-current="page"') == 1, page.name
        navs.add(nav.replace(' aria-current="page"', ""))
        assert '<html lang="en"' in text and '<main id="main">' in text, page.name
        assert 'href="#main"' in text and 'name="viewport"' in text, page.name
        assert len(re.findall(r"<h1[ >]", text)) == 1, page.name
    assert len(navs) == 1


def test_local_links_and_anchors_exist():
    ids = {page.name: set(re.findall(r'\bid="([^"]+)"', read(page))) for page in PAGES}
    for page in PAGES:
        for target in re.findall(r'(?:href|src)="([^"]+)"', read(page)):
            if target.startswith(("https://", "data:", "mailto:")):
                continue
            name, _, anchor = target.partition("#")
            name = name or page.name
            assert (SITE / name).is_file(), f"{page.name} links to {target}"
            if anchor and name.endswith(".html"):
                assert anchor in ids[name], f"{page.name} links to {target}"


def test_links_into_the_repository_point_to_tracked_paths():
    for page in PAGES:
        for path in re.findall(re.escape(GITHUB) + r"/blob/main/([^\"#]+)", read(page)):
            assert (REPO / path).is_file(), f"{page.name} links to {path}"


def test_nothing_is_loaded_from_another_site():
    for page in PAGES:
        text = read(page)
        assert not re.search(r'<(script|img|iframe|video|audio|source)[^>]+src="https?:', text), page.name
        assert not re.search(r'<link[^>]+href="https?:', text), page.name
        assert "http://" not in text.replace("http://www.w3.org/2000/svg", ""), page.name
    css = read(SITE / "style.css")
    assert "@import" not in css and "url(" not in css
    script = read(SITE / "app.js")
    assert not re.search(r"\bfetch\(|XMLHttpRequest|https?://", script)


def test_bound_numbers_use_known_keys_and_the_site_stays_small():
    for page in PAGES:
        for key in re.findall(r'data-bind="([^"]+)"', read(page)):
            assert BOUND.fullmatch(key), f"{page.name} binds {key}"
    assert sum(f.stat().st_size for f in SITE.iterdir() if f.is_file()) < 1_000_000


def test_text_colours_meet_the_contrast_target_in_both_themes():
    css = read(SITE / "style.css")
    token = re.compile(r"--([a-z-]+): (#[0-9A-Fa-f]{6});")
    first, rest = css.split("@media (prefers-color-scheme: dark)", 1)
    light = dict(token.findall(first))
    dark = light | dict(token.findall(rest.split("}\n}")[0]))
    pairs = [
        ("ink", "ground"), ("ink", "paper"), ("ink-soft", "paper"), ("ink-mute", "ground"),
        ("ink-mute", "paper"),
        ("ink-mute", "pearl"), ("ink-soft", "pearl"), ("accent", "paper"), ("accent", "ground"),
        ("accent", "accent-tint"), ("on-fill", "accent-fill"), ("good", "good-tint"), ("bad", "bad-tint"),
        ("warn", "warn-tint"), ("ink-soft", "other-tint"), ("ink", "accent-tint"), ("bad", "paper"),
    ]
    for theme in (light, dark):
        for text, background in pairs:
            ratio = contrast(theme[text], theme[background])
            assert ratio >= 4.5, (text, background, theme[text], theme[background])


def test_fixed_sentences_still_fit_the_data():
    """Some sentences around bound numbers assume a direction: "rose by", "fell by", "less often"."""
    text = read(SITE / "data.js")
    data = json.loads(text[text.index("=") + 1 :].rstrip().rstrip(";"))
    tests = {t["id"]: t for t in data["tests"]}
    assert all(tests[k]["difference"] > 0 for k in ("H3", "H5", "H7", "H8", "H10"))
    assert tests["H1"]["verdict"] == "not supported" and tests["H1"]["low"] < 0 < tests["H1"]["high"]
    assert tests["H3"]["low"] > 0 and tests["H3"]["difference"] >= tests["H3"]["threshold"]
    assert tests["H10"]["low"] < 0 < tests["H10"]["high"] and tests["H8"]["low"] < 0 < tests["H8"]["high"]
