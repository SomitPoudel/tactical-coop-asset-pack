# Previews

Generated still previews and sampled animation frames are stored here.

Still previews:
- `Previews/officer_front.png`
- `Previews/officer_side.png` (three-quarter)
- `Previews/gameplay_angle.png`
- `Previews/door_closed.png`
- `Previews/door_open.png`

Sampled animation frames are under `Previews/animations/` and remain ignored by Git by default.

Compact animated reviews are generated from those frames:
- `Previews/animations/idle_review.gif`
- `Previews/animations/walk_review.gif`
- `Previews/animations/crouch_review.gif`
- `Previews/animations/recoil_review.gif`

These four named GIFs are the only animation files allowlisted for Git tracking. The stills and GIFs are visual-review aids, not numerical validation results.

Current status:
- generated locally with Blender 5.2.2 LTS
- three-quarter animation framing includes feet and weapon contact
- doorway stills use neutral fill lighting and hide collision proxies
- rendered files have not been visually inspected in this session
