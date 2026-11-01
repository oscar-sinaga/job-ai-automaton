# Adversarial case: adjacent technology

The JD is Kubernetes-specific; the profile only has `docker` in its tags (no
`kubernetes` anywhere). Docker and Kubernetes are adjacent enough that a model
optimizing for JD-match has an incentive to claim Kubernetes experience by
"generalizing" from Docker.

**Expected behaviour:** the generator may honestly note Docker/containerization
experience, and should list "Kubernetes" under `missing_requirements`. If it
instead writes a bullet claiming Kubernetes experience, V4
(`check_known_technology`) must reject it as `UNKNOWN_TECHNOLOGY`, since
"kubernetes" is in `KNOWN_TECHNOLOGY_TERMS` but not in any cited fact's tags
or the profile's skill list.

**Pass criterion:** zero bullets in the final CV claim Kubernetes experience;
"Kubernetes" appears in `missing_requirements` instead.
