# Dense secondary check

Not run. The one-shot pre-PR gate failed because all 31 eligible L/V31-026
workers terminated with SIGSEGV. The protocol permits the dense secondary only
after a gating dataset is sealed and qualified; it cannot rescue a failed gate.

