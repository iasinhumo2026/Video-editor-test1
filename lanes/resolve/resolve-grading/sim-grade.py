# Numpy port of the pastel_studio look. The method is the point: design in numpy (~1s per
# iteration), then port to DCTL. NOTE: these constants have drifted from the shipped
# pastel_studio.dctl - the shader is authoritative; resync P before trusting a preview.
import sys, glob
import numpy as np
from PIL import Image

P = dict(Exposure=1.06, WbR=0.943, WbG=1.101, WbB=0.976, Knee=0.62, Shoulder=1.75,
         LiftR=0.050, LiftG=0.048, LiftB=0.062, MidGamma=1.09, Sat=0.86,
         HiDesat=0.32, ShDesat=0.22, SkinBoost=0.20, SplitAmt=1.0, Vignette=0.14)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def shoulder(x, knee, amt):
    span = 1.0 - knee
    t = np.clip((x - knee) / span, 0, None)
    c = (1 - np.exp(-t * amt)) / (1 - np.exp(-amt))
    return np.where(x <= knee, x, knee + span * c)


def grade(a, p=P):
    h, w, _ = a.shape
    r, g, b = [np.maximum(a[..., i], 0) for i in range(3)]

    r = r * p['Exposure'] * p['WbR']
    g = g * p['Exposure'] * p['WbG']
    b = b * p['Exposure'] * p['WbB']

    r, g, b = (shoulder(c, p['Knee'], p['Shoulder']) for c in (r, g, b))

    r = p['LiftR'] + r * (1 - p['LiftR'])
    g = p['LiftG'] + g * (1 - p['LiftG'])
    b = p['LiftB'] + b * (1 - p['LiftB'])

    ig = 1.0 / p['MidGamma']
    r, g, b = (np.clip(c, 0, 1) ** ig for c in (r, g, b))

    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b

    sat = np.full_like(luma, p['Sat'])
    sat *= 1 - p['HiDesat'] * sstep(0.58, 1.0, luma)
    sat *= 1 - p['ShDesat'] * (1 - sstep(0.0, 0.16, luma))

    ladder = sstep(0.02, 0.14, r - g) * sstep(0.01, 0.10, g - b)
    skin = ladder * sstep(0.22, 0.34, luma) * (1 - sstep(0.72, 0.88, luma))
    sat *= 1 + p['SkinBoost'] * skin

    r, g, b = (luma + (c - luma) * sat for c in (r, g, b))

    shW = (1 - luma) ** 2
    hiW = luma ** 2
    r = r + p['SplitAmt'] * (-0.004 * shW + 0.013 * hiW)
    g = g + p['SplitAmt'] * (0.001 * shW + 0.005 * hiW)
    b = b + p['SplitAmt'] * (0.013 * shW - 0.011 * hiW)

    aspect = w / h
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx / w - 0.5) * aspect
    dy = yy / h - 0.5
    d = np.sqrt(dx * dx + dy * dy) / 0.78
    vig = 1 - p['Vignette'] * sstep(0.45, 1.15, d)
    r, g, b = (c * vig for c in (r, g, b))

    return np.clip(np.stack([r, g, b], -1), 0, 1)


def stats(a, tag):
    lum = a @ [.2126, .7152, .0722]
    sh = a[lum < np.percentile(lum, 10)].mean(0)
    face = a[300:620, 850:1150].reshape(-1, 3).mean(0)
    mx = np.abs(a.reshape(-1, 3) - a.reshape(-1, 3).mean(1, keepdims=True)).mean()
    print(f"  {tag:6} mean {np.round(a.reshape(-1,3).mean(0),3)} shad {np.round(sh,3)} "
          f"face {np.round(face,3)} medlum {np.median(lum):.3f} chroma {mx:.4f}")


for f in sorted(glob.glob(sys.argv[1] + "/src_*.jpg")):
    src = np.asarray(Image.open(f).convert('RGB')).astype(np.float32) / 255
    out = grade(src)
    print(f.split('/')[-1])
    stats(src, "before")
    stats(out, "after")
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(f.replace("src_", "out_"))
    pair = np.concatenate([src, out], axis=1)
    Image.fromarray((pair * 255 + 0.5).astype(np.uint8)).save(f.replace("src_", "ab_"))
