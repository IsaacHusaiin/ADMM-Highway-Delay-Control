# Penalty Weight Sensitivity: `lambda_1`, `lambda_2`, `lambda_3`, `lambda_4`

## Purpose

This sensitivity test studies how the capacity-penalty weights affect the controller.

The penalty weights control how strongly the objective penalizes different types of capacity-related violations.

The four penalty weights are:

```text
lambda_1 = doorway overflow penalty weight
lambda_2 = safe-threshold penalty weight
lambda_3 = physical-capacity penalty weight
lambda_4 = spillback penalty weight