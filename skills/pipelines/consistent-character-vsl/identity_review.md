# Stage: identity_review

Goal: catch drift before it reaches the final cut.

Per scene: run `identity_drift` on the rendered clip's sampled frames vs the reference sheet;
also check lip-sync, black frames, aspect. Cross-scene: compare all clips to the sheet and to
each other; flag any outlier. Failed scenes auto-retry once, then escalate to the user.
Before `compose`, block if identity is broken or the cut is slideshow-y. Apply a unifying color
grade at `edit` so separate generations feel like one shoot.
