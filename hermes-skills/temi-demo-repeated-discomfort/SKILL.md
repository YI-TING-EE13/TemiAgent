# Temi Demo Repeated Discomfort Skill

This root-owned private-Demo skill is enabled only together with explicit Demo
operator identity. It can operate only while Bridge context confirms `father`.
It does not diagnose, assess severity, measure blood pressure, or access the
mother or unknown partitions.

## Exact flow

After optional `小安小安` and punctuation removal, match only:

1. `我又不舒服了`、`我又不太舒服`、`我又覺得不舒服` →
   `retrieve_repeated_discomfort()`.
2. After Bridge callback confirms the synthetic prior event was retrieved,
   `對`、`是`、`是的` → `confirm_repeated_headache()`.
3. After that callback confirms, only `血壓<2-3 digits>/<2-3 digits>` or the
   full-width slash form → `record_repeated_blood_pressure` with the exact
   user transcript and parsed integers.

The callback reads only the seeded father headache event and appends a new
father event only after confirmation and a successful canonical memory API
write. Any failed callback must not claim that a record was written. A resident
tool never reads files or publishes MQTT directly.
