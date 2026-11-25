# Model Boundaries and Deviations from ERCOT Practice

The repository uses ERCOT data but is a stylized operating game.

1. A DAM energy award is a cleared financial/settlement quantity, not a physical
   minimum-output instruction here. It is retained as `b_dam` but is not mixed
   with COP HSL or imposed as a constraint.
2. COP HSL represents an availability plan/forecast. Forecast error is not
   automatically misconduct or noncompliance.
3. The shared POI allocation is a designed proportional realization rule, not a
   claim about ERCOT dispatch of co-located resources.
4. The 100 $/MWh attempted-overflow charge is a fixed internal strategic rule,
   not an ERCOT fee, and is excluded from system value.
5. `PRICE` remains in cell IDs for compatibility with the slide table, but the
   revised factor is an aggregate injection signal, not a congestion price.
6. The model is price taking and omits endogenous clearing, ancillary services,
   unit commitment, outages, losses, and a full two-settlement implementation.
7. Wind-only battery charging is used because this model has an export POI limit
   but no corresponding import constraint.

The separate monitor module's `shortfall` is a statistical forecast residual;
it is not the removed operating-game delivery obligation.
