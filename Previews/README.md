# Previews

Generated still previews and sampled animation frames are stored here.

Still previews:
- `Previews/officer_front.png`
- `Previews/officer_side.png` (true profile)
- `Previews/officer_three_quarter.png`
- `Previews/officer_boots_knees.png`
- `Previews/officer_standing_crouched.png`
- `Previews/gameplay_angle.png`
- `Previews/door_closed.png`
- `Previews/door_open.png`

Sampled animation frames are under `Previews/animations/` and remain ignored by Git by default.

Compact animated reviews are generated from those frames:
- `Previews/animations/idle_review.gif`
- `Previews/animations/walk_review.gif`
- `Previews/animations/stand_to_crouch_review.gif`
- `Previews/animations/crouch_review.gif`
- `Previews/animations/crouch_to_stand_review.gif`
- `Previews/animations/stance_transition_review.gif`
- `Previews/animations/recoil_review.gif`

The before/after pairs under `Previews/review/` use matching front, side, three-quarter, boots/knees, gameplay-distance and standing/crouched views. Officer views include a ground grid; transition, crouch, walk and recoil GIF timings derive from authored Blender frame numbers at 24 fps. Loop endpoints are omitted only for looped actions. The stills and GIFs are visual-review aids, not numerical validation results.

Current status:
- generated locally with Blender 5.2.2 LTS
- before/after image sets use matching front, side, three-quarter, boot/knee and standing/crouched views
- a temporary ground grid makes foot contact legible in review renders
- doorway stills use neutral fill lighting and hide collision proxies
- rendered files have not been visually inspected in this session
