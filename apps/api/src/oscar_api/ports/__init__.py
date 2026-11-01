"""Interfaces only. Domain modules depend on these, never on `adapters/`
directly (docs/03 §2) -- that's what makes the LLM provider and storage
swappable and lets tests inject fakes instead of hitting the network."""
