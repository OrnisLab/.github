#!/usr/bin/env python3
"""Build the OrnisLab profile assets: cover banner, domain cards and org avatar.

Inputs (tools/brand/):
    ornis-guard-white.png   Ornis Guard logo, white on transparent
    ornis-vista-white.png   Ornis Vista logo, white on transparent
    ornis-recon.png         Ornis Recon logo (any colour; recoloured to white here)
    isnet-white.png         optional: İşNet logo, white on transparent. Without it,
                            the logo is lifted from cover-concept.jpg (low resolution).
    cover-concept.jpg       LinkedIn cover the banner is modelled on

Outputs (profile/assets/):
    banner.svg, card-{guard,vista,recon,secops}.svg, avatar.svg, avatar.png
    brand/ornis-recon-white.png

Text is converted to outlines and logos are embedded, so every SVG is self-contained.
(GitHub shows README images through <img>, which cannot load fonts or external files.)

Font: Plus Jakarta Sans, SIL Open Font License 1.1 (tools/fonts/).

Usage:
    pip install fonttools uharfbuzz pillow numpy scipy
    python3 tools/build_assets.py
To change wording, edit CONTENT below and re-run.
"""
from __future__ import annotations

import base64
import html
import io
import pathlib
import random
import subprocess

import numpy as np
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "tools" / "fonts"
BRAND = ROOT / "tools" / "brand"
OUT = ROOT / "profile" / "assets"

# --------------------------------------------------------------------------- content

CONTENT = {
    "headline": ["Open Research Network", "for Intelligent Security"],
    "descriptor": "Open-source security tools from the Ornis cybersecurity family",
    "logo_caption": "OPEN SOURCE LAB",
    "cards": [
        {
            "slug": "guard", "logo": "ornis-guard-white.png",
            "kicker": "SOC, SOAR and MDR operations",
            "body": "Detection content, SOAR playbooks and triage tools from "
                    "Ornis Guard, built for running MDR operations.",
        },
        {
            "slug": "vista", "logo": "ornis-vista-white.png",
            "kicker": "Vulnerability and exposure management",
            "body": "Asset discovery, scan orchestration and exposure reporting "
                    "utilities from Ornis Vista.",
        },
        {
            "slug": "recon", "logo": "ornis-recon.png",
            "kicker": "Cyber threat intelligence",
            "body": "Collectors, enrichment and IOC pipelines that turn raw feeds "
                    "into actionable intelligence, from Ornis Recon.",
        },
        {
            "slug": "secops", "logo": None, "title": "SecOps",
            "kicker": "Open source in our SOC",
            "body": "The open-source stack behind İşNet’s SOC, shared with "
                    "our configs, integrations and playbooks.",
        },
    ],
}

# Dark: colours sampled from the cover concept. Light: the same scene on a pale sky, with the
# logos in Ornis brand blues (sampled from the Ornis Recon logo).
THEMES = {
    "dark": dict(
        bg="#070B16", panel="#0A1322", line="#1B2A3F", glow="#144353", glow2="#0E2A38",
        orbit="#4B8A9C", star="#9CCAD8", text="#FFFFFF", body="#C7D3E0", mute="#8EA3B8",
        blue="#5C98FA", logo_a="#FFFFFF", logo_b="#FFFFFF", isnet="#FFFFFF",
        halo=.55, orbit_k=1.0, spark="#DDEBFF", frame=False,
    ),
    "light": dict(
        bg="#F6F9FD", panel="#FFFFFF", line="#D5E1EE", glow="#CFE2F7", glow2="#E3EDF9",
        orbit="#5F8FC4", star="#6E98C8", text="#0B1F4D", body="#3A4C63", mute="#5B6E86",
        blue="#1C61CA", logo_a="#0030BA", logo_b="#1C61CA", isnet="#0B1F4D",
        halo=0, orbit_k=1.25, spark="#1C61CA", frame=True,
    ),
}
C = dict(THEMES["dark"])  # the theme being built; main() swaps it

# --------------------------------------------------------------------------- type


def fmt(v: float) -> str:
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Face:
    """One static weight of Plus Jakarta Sans: shaping via HarfBuzz, outlines via fontTools."""

    def __init__(self, weight: int):
        path = FONTS / f"PlusJakartaSans-{weight}.ttf"
        if not path.exists():
            instancer.instantiateVariableFont(
                TTFont(FONTS / "PlusJakartaSans.ttf"), {"wght": weight}
            ).save(path)
        self.tt = TTFont(path)
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.upem = self.tt["head"].unitsPerEm
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()

    def _shape(self, s: str):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, s: str, size: float, tracking: float = 0.0) -> float:
        infos, pos = self._shape(s)
        return sum(p.x_advance for p in pos) * size / self.upem + tracking * size * (len(infos) - 1)

    def outline(self, s, size, x, y, tracking=0.0):
        infos, pos = self._shape(s)
        k = size / self.upem
        pen_x, out = x, []
        for info, p in zip(infos, pos):
            svg = SVGPathPen(self.glyphs, ntos=fmt)
            self.glyphs[self.order[info.codepoint]].draw(
                TransformPen(svg, (k, 0, 0, -k, pen_x + p.x_offset * k, y - p.y_offset * k))
            )
            if d := svg.getCommands():
                out.append(d)
            pen_x += p.x_advance * k + tracking * size
        return out


FACES: dict[int, Face] = {}


def face(w: int) -> Face:
    if w not in FACES:
        FACES[w] = Face(w)
    return FACES[w]


def text(s, *, size, x, y, weight=400, fill="#fff", tracking=0.0, anchor="start", opacity=None):
    f = face(weight)
    if anchor != "start":
        w = f.width(s, size, tracking)
        x -= w / 2 if anchor == "middle" else w
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return f'<path fill="{fill}"{op} d="{"".join(f.outline(s, size, x, y, tracking))}"/>'


def wrap(s, *, size, weight, width):
    f, lines, cur = face(weight), [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if f.width(trial, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur]


# --------------------------------------------------------------------------- logos


def load_white(name: str) -> Image.Image:
    """Logo as pure white on transparent, trimmed to its ink."""
    im = Image.open(BRAND / name).convert("RGBA")
    a = np.array(im)
    a[..., :3] = 255
    im = Image.fromarray(a)
    return im.crop(im.getbbox())


def tint(im: Image.Image, split: int, left: str, right: str) -> Image.Image:
    """Recolour a logo mask: columns before `split` get `left`, the rest `right`."""
    a = np.array(im)
    for colour, cols in ((left, slice(0, split)), (right, slice(split, None))):
        a[:, cols, :3] = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    return Image.fromarray(a)


def ornis_end(im: Image.Image) -> int:
    """x where the shared bird + 'ornis' part ends: the widest gap starting in the first 65 %."""
    ink = (np.array(im)[..., 3] > 40).any(0)
    best, start = (0, 0), None
    for x, on in enumerate(ink):
        if not on and start is None:
            start = x
        elif on and start is not None:
            if start < len(ink) * .65:
                best = max(best, (x - start, start))
            start = None
    return best[1]


def bird_only(im: Image.Image) -> Image.Image:
    """The three-bird mark: connected shapes that start left of the letter 'o'."""
    a = np.array(im)
    labels, _ = ndimage.label(a[..., 3] > 20)
    blobs = sorted((sl[1].start, sl[1].stop, i + 1) for i, sl in enumerate(ndimage.find_objects(labels)))
    # the 'o' is the first sizeable blob that starts right of 15 % of the width
    o_left = next(x0 for x0, x1, _ in blobs if x0 > im.width * .15 and x1 - x0 > im.width * .05)
    keep = np.isin(labels, [lab for x0, _, lab in blobs if x0 < o_left - 5])
    a[..., 3] = np.where(ndimage.binary_dilation(keep, iterations=2), a[..., 3], 0)
    out = Image.fromarray(a)
    return out.crop(out.getbbox())


def isnet_logo() -> Image.Image:
    if (BRAND / "isnet-white.png").exists():
        return load_white("isnet-white.png")
    g = np.array(Image.open(BRAND / "cover-concept.jpg").convert("L")).astype(float)
    reg = g[18:52, 40:150]
    bg = np.median(reg)
    m = Image.fromarray((np.clip((reg - bg - 8) / (240 - bg - 8), 0, 1) * 255).astype("uint8"))
    m = m.crop(m.getbbox())
    m = m.resize((m.width * 4, m.height * 4), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2))
    arr = np.clip((np.array(m).astype(float) / 255 - 0.12) / 0.6, 0, 1)
    out = Image.new("RGBA", m.size, (255, 255, 255, 0))
    out.putalpha(Image.fromarray((arr * 255).astype("uint8")))
    return out


def img_tag(im: Image.Image, x, y, w, *, px_width=None, extra=""):
    """Embed a PNG; px_width sets the stored resolution (default 3x the drawn width)."""
    target = int(px_width or w * 3)
    if im.width > target:
        im = im.resize((target, round(im.height * target / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    h = w * im.height / im.width
    data = base64.b64encode(buf.getvalue()).decode()
    return (f'<image x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"{extra} '
            f'href="data:image/png;base64,{data}"/>'), h


# --------------------------------------------------------------------------- scenery


def glow(uid, cx, cy, rx, ry, *, strength=1.0):
    return (
        f'<radialGradient id="g{uid}" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{rx}" '
        f'gradientTransform="translate({cx} {cy}) scale(1 {fmt(ry / rx)}) translate({-cx} {-cy})">'
        f'<stop offset="0" stop-color="{C["glow"]}" stop-opacity="{strength}"/>'
        f'<stop offset=".5" stop-color="{C["glow2"]}" stop-opacity="{strength * .6:.2f}"/>'
        f'<stop offset="1" stop-color="{C["bg"]}" stop-opacity="0"/></radialGradient>'
        f'<rect x="{cx - rx}" y="{cy - ry}" width="{2 * rx}" height="{2 * ry}" fill="url(#g{uid})"/>'
    )


def ellipse_path(cx, cy, rx, ry):
    return (f"M{fmt(cx - rx)} {fmt(cy)}A{fmt(rx)} {fmt(ry)} 0 1 1 {fmt(cx + rx)} {fmt(cy)}"
            f"A{fmt(rx)} {fmt(ry)} 0 1 1 {fmt(cx - rx)} {fmt(cy)}")


def stars(rng, n, box, avoid=()):
    x0, y0, x1, y1 = box
    out = []
    while len(out) < n:
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if any(ax0 < x < ax1 and ay0 < y < ay1 for ax0, ay0, ax1, ay1 in avoid):
            continue
        r = rng.choice([0.9, 1.1, 1.4, 1.8])
        out.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{r}" fill="{C["star"]}" '
                   f'fill-opacity="{rng.uniform(.25, .65):.2f}"/>')
    return "".join(out)


BLUR = '<filter id="soft" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="{s}"/></filter>'


def svg_doc(w, h, title, body, *, desc=""):
    title, desc = html.escape(title, quote=False), html.escape(desc, quote=False)
    d = f"<desc>{desc}</desc>" if desc else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="t"><title id="t">{title}</title>{d}{body}</svg>\n')


# --------------------------------------------------------------------------- builders


def build_banner(ornis, word_start):
    W, H = 1280, 320
    rng = random.Random(11)
    orbit = ellipse_path(560, 150, 560, 118)
    k = C["orbit_k"]
    lx, ly, logo_w = 862, 92, 352
    ornis = tint(ornis, ornis.width, C["logo_a"], C["logo_a"])
    logo, logo_h = img_tag(ornis, lx, ly, logo_w)
    halo = ""
    if C["halo"]:
        halo, _ = img_tag(ornis, lx, ly, logo_w, px_width=400,
                          extra=f' filter="url(#soft)" opacity="{C["halo"]}"')
    mark = isnet_logo()
    isnet, _ = img_tag(tint(mark, mark.width, C["isnet"], C["isnet"]), 56, 34, 92, px_width=368)
    word_x0 = lx + logo_w * word_start

    body = [
        "<style>.spark{offset-path:path('" + orbit + "');offset-rotate:0deg;"
        "animation:orbit 26s linear infinite}"
        "@keyframes orbit{from{offset-distance:0%}to{offset-distance:100%}}"
        "@media (prefers-reduced-motion:reduce){.spark{animation:none;offset-distance:38%}}</style>",
        f'<defs><clipPath id="c"><rect width="{W}" height="{H}" rx="18"/></clipPath>{BLUR.format(s=7)}</defs>',
        f'<rect width="{W}" height="{H}" rx="18" fill="{C["bg"]}"/>',
        '<g clip-path="url(#c)">',
        glow("a", 600, 150, 640, 230),
        glow("b", 1040, 150, 300, 150, strength=.7),
        f'<g fill="none" stroke="{C["orbit"]}" stroke-width="1.1">'
        f'<path d="{orbit}" stroke-opacity="{.28 * k:.2f}"/>'
        f'<path d="{ellipse_path(640, 168, 470, 84)}" stroke-opacity="{.16 * k:.2f}" transform="rotate(-3 640 168)"/>'
        f'<path d="{ellipse_path(760, 150, 700, 190)}" stroke-opacity="{.10 * k:.2f}"/></g>',
        stars(rng, 26, (20, 14, W - 20, H - 14), avoid=[(40, 100, 700, 270), (840, 70, 1240, 250)]),
        f'<g class="spark"><circle r="9" fill="{C["blue"]}" fill-opacity=".18"/>'
        f'<circle r="2.6" fill="{C["spark"]}"/></g>',
        halo, logo,
        text(CONTENT["logo_caption"], size=13, x=word_x0 + (lx + logo_w - word_x0) / 2, y=ly + logo_h + 34,
             weight=600, fill=C["body"], tracking=0.32, anchor="middle", opacity=.8),
        "</g>",
        f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" '
        f'stroke="{C["line"]}" stroke-width="1.5"/>' if C["frame"] else "",
        isnet,
        text(CONTENT["headline"][0], size=46, x=54, y=152, weight=700, fill=C["text"], tracking=-0.015),
        text(CONTENT["headline"][1], size=46, x=54, y=208, weight=700, fill=C["blue"], tracking=-0.015),
        text(CONTENT["descriptor"], size=18, x=56, y=254, weight=500, fill=C["mute"]),
    ]
    return svg_doc(W, H, "OrnisLab — Open Research Network for Intelligent Security", "".join(body),
                   desc=CONTENT["descriptor"])


def build_card(card, scale, bird):
    W, H = 640, 212
    uid = card["slug"]
    if card["logo"]:
        im = load_white(card["logo"])
        im = tint(im, ornis_end(im), C["logo_a"], C["logo_b"])
        logo, _ = img_tag(im, 32, 32, im.width * scale)
    else:
        bw, bh = bird.width * scale, bird.height * scale
        logo, _ = img_tag(tint(bird, bird.width, C["logo_a"], C["logo_a"]), 32, 32, bw)
        logo += text(card["title"], size=36, x=32 + bw + 14, y=32 + bh * .86, weight=700,
                     fill=C["logo_b"], tracking=-0.01)
    lines = wrap(card["body"], size=19, weight=400, width=W - 64)
    if len(lines) > 2:
        raise SystemExit(f'Card "{uid}": description needs {len(lines)} lines; keep it to 2.')
    body = [
        f'<defs><clipPath id="k{uid}"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="15"/></clipPath></defs>',
        f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="16" fill="{C["panel"]}" '
        f'stroke="{C["line"]}" stroke-width="1.5"/>',
        f'<g clip-path="url(#k{uid})">{glow(uid, 560, 10, 300, 150, strength=.75)}'
        f'<path d="{ellipse_path(470, 40, 340, 64)}" fill="none" stroke="{C["orbit"]}" '
        f'stroke-opacity="{.18 * C["orbit_k"]:.2f}" stroke-width="1.1"/></g>',
        logo,
        text(card["kicker"], size=17, x=32, y=124, weight=600, fill=C["blue"]),
        *(text(line, size=19, x=32, y=158 + i * 27, weight=400, fill=C["body"])
          for i, line in enumerate(lines)),
    ]
    title = f'Ornis {uid.title()}' if card["logo"] else card["title"]
    return svg_doc(W, H, f'{title} — {card["kicker"]}', "".join(body), desc=card["body"])


def build_avatar(bird):
    S, w = 512, 340
    bird = tint(bird, bird.width, C["logo_a"], C["logo_a"])
    h = w * bird.height / bird.width
    y = (S - h) / 2 + 6
    mark, _ = img_tag(bird, (S - w) / 2, y, w, px_width=1020)
    halo = ""
    if C["halo"]:
        halo, _ = img_tag(bird, (S - w) / 2, y, w, px_width=400,
                          extra=f' filter="url(#soft)" opacity="{C["halo"] + .05:.2f}"')
    body = [
        f'<defs>{BLUR.format(s=10)}</defs>',
        f'<rect width="{S}" height="{S}" fill="{C["bg"]}"/>',
        glow("v", 256, 262, 300, 230),
        f'<path d="{ellipse_path(256, 300, 300, 92)}" fill="none" stroke="{C["orbit"]}" '
        f'stroke-opacity="{.28 * C["orbit_k"]:.2f}" stroke-width="2" transform="rotate(-8 256 300)"/>',
        stars(random.Random(3), 10, (20, 20, 492, 492), avoid=[(70, 120, 450, 400)]),
        halo, mark,
    ]
    return svg_doc(S, S, "OrnisLab", "".join(body))


def main():
    (OUT / "brand").mkdir(parents=True, exist_ok=True)

    # The white Recon logo is also a deliverable in its own right.
    load_white("ornis-recon.png").save(OUT / "brand" / "ornis-recon-white.png", optimize=True)

    vista = load_white("ornis-vista-white.png")
    ornis = vista.crop((0, 0, ornis_end(vista), vista.height))
    ornis = ornis.crop(ornis.getbbox())
    bird = bird_only(ornis)
    word_start = (bird.width + 10) / ornis.width

    # One scale for every product logo, so 'ornis' is the same size on each card.
    target = 180  # drawn width of bird + 'ornis'
    scales = {c["slug"]: target / ornis_end(load_white(c["logo"])) for c in CONTENT["cards"] if c["logo"]}
    bird_scale = target / ornis.width

    for theme, colours in THEMES.items():
        C.clear()
        C.update(colours)
        (OUT / f"banner-{theme}.svg").write_text(build_banner(ornis, word_start), encoding="utf-8")
        for card in CONTENT["cards"]:
            svg = build_card(card, scales.get(card["slug"], bird_scale), bird)
            (OUT / f'card-{card["slug"]}-{theme}.svg').write_text(svg, encoding="utf-8")
        avatar = OUT / f"avatar-{theme}.svg"
        avatar.write_text(build_avatar(bird), encoding="utf-8")
        subprocess.run(["rsvg-convert", "-w", "512", str(avatar), "-o", str(avatar.with_suffix(".png"))],
                       check=False)
    for p in sorted(OUT.rglob("*.*")):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
