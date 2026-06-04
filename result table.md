| Policy                  | Released (veh) | Queued end (veh) | Spilled (veh) | Served % | Spill % | ML exit flow from Cell 8 (veh) | Mainline delay (veh-min) | Local delay (veh-min) |
| ----------------------- | -------------: | ---------------: | ------------: | -------: | ------: | -----------------------------: | -----------------------: | --------------------: |
| Baseline (= Fixed 1.0x) |         4200.0 |            278.5 |        1821.5 |    66.7% |   28.9% |                        10119.2 |                  72848.7 |               15225.7 |
| Greedy ADMM             |         4188.7 |            278.5 |        1832.8 |    66.5% |   29.1% |                        10119.2 |                  72262.9 |               15313.2 |
| Fixed 0.9x              |         3780.0 |            278.5 |        2241.5 |    60.0% |   35.6% |                        10119.2 |                  60496.5 |               15458.9 |
| Fixed 0.8x              |         3360.0 |            278.5 |        2661.5 |    53.3% |   42.2% |                        10119.2 |                  48243.2 |               15626.3 |
| ADMM-MPC                |         3290.6 |            278.5 |        2730.9 |    52.2% |   43.3% |                        10119.2 |                  44529.5 |               15916.4 |
| Fixed 0.7x              |         2940.0 |            278.5 |        3081.5 |    46.7% |   48.9% |                        10119.2 |                  35905.6 |               15751.5 |


| Policy                  | Total system delay (veh-min) | Fairness penalty | Doorway penalty | Safe penalty | Physical penalty | Spillback penalty |
| ----------------------- | ---------------------------: | ---------------: | --------------: | -----------: | ---------------: | ----------------: |
| Baseline (= Fixed 1.0x) |                      88074.3 |           25.453 |          5712.1 |    1410495.4 |              0.0 |            3454.2 |
| Greedy ADMM             |                      87576.1 |           21.490 |          5606.8 |    1391914.4 |              0.0 |            3469.5 |
| Fixed 0.9x              |                      75955.4 |           21.690 |          4450.1 |     905688.0 |              0.0 |            5088.1 |
| Fixed 0.8x              |                      63869.5 |           19.071 |          3388.2 |     459165.0 |              0.0 |            7039.3 |
| ADMM-MPC                |                      60445.9 |            3.307 |          1088.3 |     522358.5 |              0.0 |            7330.1 |
| Fixed 0.7x              |                      51657.1 |           17.157 |          2484.9 |       2708.8 |              0.0 |            9300.8 |

| Policy                  | Capacity penalty (total) | Raw objective | Normalized objective | Obj vs baseline % | Sys delay vs baseline % |
| ----------------------- | -----------------------: | ------------: | -------------------: | ----------------: | ----------------------: |
| Baseline (= Fixed 1.0x) |                1419661.7 |     1507761.5 |               34.000 |              0.0% |                    0.0% |
| Greedy ADMM             |                1400990.8 |     1488588.3 |               33.586 |             -1.2% |                   -0.6% |
| Fixed 0.9x              |                 915226.2 |      991203.4 |               28.617 |            -15.8% |                  -13.8% |
| Fixed 0.8x              |                 469592.5 |      533481.1 |               23.418 |            -31.1% |                  -27.5% |
| ADMM-MPC                |                 530777.0 |      591226.2 |               20.950 |            -38.4% |                  -31.4% |
| Fixed 0.7x              |                  14494.5 |       66168.7 |               18.277 |            -46.2% |                  -41.3% |

|Column|Simple meaning|
|---|---|
|**Released (veh)**|How many ramp vehicles were allowed onto the freeway.|
|**Queued end (veh)**|How many ramp vehicles were still waiting at the end.|
|**Spilled (veh)**|How many ramp vehicles could not fit in ramp storage and spilled back.|
|**Served %**|Percent of ramp demand that was actually released onto the freeway.|
|**Spill %**|Percent of ramp demand that became spillback.|
|**ML exit flow from Cell 8 (veh)**|How many vehicles exited the modeled freeway corridor from the last cell.|
|**Mainline delay (veh-min)**|Total freeway delay inside the mainline cells. Lower is better.|
|**Local delay (veh-min)**|Total ramp-side waiting delay. Lower is better.|
|**Total system delay (veh-min)**|Mainline delay + local delay. Lower is better.|
|**Fairness penalty**|Measures how uneven ramp queues are across ramps. Lower means ramp burden is more balanced.|
|**Doorway penalty**|Penalty when too many vehicles try to enter a freeway cell at once. Lower is better.|
|**Safe penalty**|Penalty when freeway cell occupancy goes above the safe congestion threshold. Lower is better.|
|**Physical penalty**|Penalty when freeway cell occupancy exceeds physical storage capacity. Should ideally be 0.|
|**Spillback penalty**|Penalty for ramp overflow onto local roads. Lower is better.|
|**Capacity penalty (total)**|Doorway + safe + physical + spillback penalties.|
|**Raw objective**|Total system score before normalization. Includes delay + fairness + capacity penalties. Lower is better.|
|**Normalized objective**|Scaled version of the objective, easier to compare across policies. Lower is better.|
|**Obj vs baseline %**|Percent improvement/worsening in normalized objective compared with baseline. Negative means better.|
|**Sys delay vs baseline %**|Percent improvement/worsening in total system delay compared with baseline. Negative means better.|