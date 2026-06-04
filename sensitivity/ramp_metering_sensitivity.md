# Meter-Capacity Sensitivity

## Purpose

This sensitivity test studies how the ramp meter-capacity limit affects controller behavior.

The meter-capacity rule is:

$$
u_{i,t}
\le
c
\cdot
u_{i,t}^{observed}
$$

where:

$$
u_{i,t}
$$

is the optimized ramp release,

$$
c
$$

is the meter-capacity multiplier, and

$$
u_{i,t}^{observed}
$$

is the observed ramp release from the benchmark input series.

---

## Meaning of the Meter-Capacity Multiplier

The parameter \(c\) controls how much authority the controller has over ramp releases.

If:

$$
c = 1.0
$$

then the controller can release up to the observed ramp-release level.

If:

$$
c < 1.0
$$

then the controller is forced to meter more aggressively than the observed release.

In simple terms:

```text
larger c  = weaker metering restriction
smaller c = stronger metering restriction