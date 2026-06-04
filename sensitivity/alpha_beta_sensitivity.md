# Delay Weight Sensitivity: `alpha_main` and `beta_local`

## Purpose

This sensitivity test studies how the delay-priority weights affect the controller behavior.

The two tested weights are:

- `alpha_main`: priority weight for freeway mainline delay
- `beta_local`: priority weight for ramp/local delay

The purpose is to check whether changing these weights meaningfully changes the optimized ramp-metering decisions, or whether the controller behavior is mainly driven by other constraints such as meter capacity, ramp storage