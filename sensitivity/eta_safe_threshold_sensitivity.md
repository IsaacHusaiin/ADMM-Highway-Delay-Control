# Safe-Threshold Sensitivity: `eta`

## Purpose

This sensitivity test studies how changing the safe-threshold parameter `eta` affects the CTM penalty behavior.

The safe-threshold capacity is defined as:

$$
X_{\text{safe},i}
=
\eta
\cdot
N_{\max,i}
$$

where:

$$
X_{\text{safe},i}
$$

is the safe operating threshold for cell \(i\),

$$
\eta
$$

is the safe-threshold multiplier, and

$$
N_{\max,i}
$$

is the physical storage capacity of cell \(i\).

---

## Meaning of `eta`

The parameter `eta` controls how strict the safe-threshold rule is.

A larger value of `eta` means the safe threshold is looser:

$$
\eta \uparrow
\Rightarrow
X_{\text{safe}} \uparrow
$$

A smaller value of `eta` means the safe threshold is tighter:

$$
\eta \downarrow
\Rightarrow
X_{\text{safe}} \downarrow
$$

So:

```text
larger eta  = cells can hold more vehicles before safe penalty activates
smaller eta = safe penalty activates earlier