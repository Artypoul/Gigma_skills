# Session State

| State | Meaning | Required next action |
| --- | --- | --- |
| `assessing` | Evidence is being gathered. | Read the narrow source needed to choose a path. |
| `ready_to_act` | Outcome and safe scope are clear. | Perform the reversible in-scope step. |
| `awaiting_confirmation` | External, destructive, or product-defining action needs approval. | Ask one concrete question and do not perform that action. |
| `waiting_on_external` | A real CI, monitor, or service result is pending. | Observe success, failure, cancellation, timeout, and unknown state through the available mechanism; silence is not success. |
| `verifying` | Work was performed. | Run the appropriate proof. |
| `complete` | Proof supports the requested result. | Give outcome-first handoff. |
| `blocked` | Progress needs user input or external state. | State the exact missing input/state and stop. |

Use state names as internal control, not as unnecessary jargon in every user response.

## Confirmation Binding

An `awaiting_confirmation` or `blocked` state is released only by a reply that directly answers the
named blocker after the affected targets and risk were shown. For example, after asking whether to
write over specific dirty files, `потом review, PR, merge и deploy` leaves the state blocked because
it authorizes no current write. Ask the same narrow question once more; do not advance to
`ready_to_act` by inference.
